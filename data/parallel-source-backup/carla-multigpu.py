#!/usr/bin/env python3
"""Supervise a CARLA primary and one independent Vulkan renderer per GPU."""
import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import time

import carla

ROOT = Path('/media/william/mist1/Simulations')
LINUX = Path('/mnt/simulations')


def commands(gpus, port, backend):
    common = [str(LINUX / 'bin/carla-sim'), '-unattended', '-nosound', '-log']
    result = [('primary', common + [f'-carla-rpc-port={port}', '-nullrhi'])]
    settings = ['r.Streaming.PoolSize 2000', 'r.RayTracing.UseReferenceBasedResidency 1',
                'r.RayTracing.NumAlwaysResidentLODs 0,r.RayTracing.ResidentGeometryMemoryPoolSizeInMB 2048', 'carla.Sensors.GpuRayTracing ' + ('1' if backend == 'gpu' else '0')]
    if backend == 'gpu':
        settings += ['r.RayTracing.ExternalQueries 1', 'r.RayTracing.ExternalQueryBounds 1',
                     'r.RayTracing.ForceAllRayTracingEffects 0', 'r.RayTracing.Culling 0',
                     'r.RayTracing.Geometry.InstancedStaticMeshes.Culling 0']
    for worker, gpu in enumerate(gpus):
        result.append((f'gpu-{gpu}', common + [
            f'-carla-rpc-port={port + 10 * (worker + 1)}',
            '-carla-primary-host=127.0.0.1', f'-carla-primary-port={port + 2}',
            f'-graphicsadapter={gpu}', '-RenderOffScreen', '-ResX=160', '-ResY=90',
            '-quality-level=High', '-ExecCmds=' + ','.join(settings)]))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gpus', default='3', help='Vulkan adapter indices, one worker each')
    p.add_argument('--port', type=int, default=2000)
    p.add_argument('--backend', choices=['gpu', 'cpu'], default='gpu')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    try:
        gpus = [int(x) for x in args.gpus.split(',')]
        assert gpus and len(set(gpus)) == len(gpus) and min(gpus) >= 0
        assert 1024 <= args.port <= 65000 - 10 * len(gpus)
    except (ValueError, AssertionError):
        p.error('Use distinct nonnegative GPU indices and a valid unprivileged port.')
    launch = commands(gpus, args.port, args.backend)
    if args.dry_run:
        print(json.dumps([{'role': role, 'command': cmd} for role, cmd in launch], indent=2))
        return
    editor = LINUX / 'UnrealEngine5_carla/Engine/Binaries/Linux/UnrealEditor'
    if not editor.is_file():
        p.error('UnrealEditor is not built yet. Run simulations-status for build progress.')
    # Check every reserved port before creating any child processes.
    probes = []
    try:
        for offset in [0] + [10 * (i + 1) for i in range(len(gpus))]:
            for extra in range(3):
                sock = socket.socket()
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('0.0.0.0', args.port + offset + extra))
                probes.append(sock)
    except OSError as error:
        p.error(f'CARLA port is already in use: {error}')
    finally:
        for sock in probes:
            sock.close()
    output = ROOT / 'logs' / time.strftime('multigpu-%Y%m%d-%H%M%S')
    output.mkdir(parents=True)
    children = []
    handles = []

    def stop(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for role, cmd in launch:
            (output / (role + '.log')).touch(exist_ok=True)
            cmd = cmd + ['-abslog=' + str(output / (role + '.log'))]
            handle = (output / (role + '-stdout.log')).open('wb')
            handles.append(handle)
            child = subprocess.Popen(cmd, cwd=LINUX, stdout=handle, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            children.append((role, child))
            print(f'{role}: PID {child.pid}; log {output / (role + ".log")}', flush=True)
            if role == 'primary':
                deadline = time.monotonic() + 600
                while True:
                    if child.poll() is not None:
                        raise RuntimeError('Primary exited during startup; inspect its log.')
                    try:
                        # The primary is the only client-controlled world. Pause
                        # it in fixed-step mode before waiting for worker loading.
                        client = carla.Client('127.0.0.1', args.port)
                        client.set_timeout(5)
                        world = client.get_world()
                        world.get_map()
                        settings = world.get_settings()
                        settings.synchronous_mode = True
                        settings.fixed_delta_seconds = 0.05
                        world.apply_settings(settings)
                        break
                    except (OSError, RuntimeError):
                        if time.monotonic() > deadline:
                            raise TimeoutError('Primary world did not become ready within 10 minutes.')
                        time.sleep(1)
        manifest = {
            'backend': args.backend, 'primary_port': args.port, 'manager_pid': os.getpid(),
            'ready': False,
            'children': [{'role': r, 'pid': c.pid, 'command': c.args} for r, c in children]}

        def save_manifest():
            temporary = output / 'processes.json.next'
            temporary.write_text(json.dumps(manifest, indent=2))
            temporary.replace(output / 'processes.json')

        save_manifest()
        print('Waiting for worker maps and renderer warmup...', flush=True)
        deadline = time.monotonic() + 1800
        while True:
            for role, child in children:
                if child.poll() is not None:
                    raise RuntimeError(f'{role} exited during initialization; inspect {output}')
            if all('Engine is initialized. Leaving FEngineLoop::Init()' in
                   (output / (role + '.log')).read_text(errors='replace') for role, _ in children):
                break
            if time.monotonic() > deadline:
                raise TimeoutError('Worker map initialization exceeded 30 minutes')
            time.sleep(2)
        client.set_timeout(180)
        for _ in range(30):
            world.tick()
            time.sleep(0.5)
        manifest['ready'] = True
        save_manifest()
        print('READY: primary and GPU workers initialized.\n'
              'Use synchronous mode and consume every sensor frame before the next tick.\n'
              'Multiple sensor subscriptions are assigned across the selected GPUs.\n'
              'Press Ctrl-C to stop this group.', flush=True)
        while True:
            for role, child in children:
                if child.poll() is not None:
                    raise RuntimeError(f'{role} exited with code {child.returncode}; inspect {output}')
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        # Only terminate the process groups created by this invocation.
        for _, child in reversed(children):
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        deadline = time.monotonic() + 30
        for _, child in reversed(children):
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        for handle in handles:
            handle.close()


if __name__ == '__main__':
    main()
