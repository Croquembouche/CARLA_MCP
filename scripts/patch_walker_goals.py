from pathlib import Path
import shutil
root=Path('/mnt/simulations/carla/LibCarla/source/carla/nav');backup=Path('data/reliability-backup/walker');backup.mkdir(exist_ok=True)
for name in ['WalkerManager.h','WalkerManager.cpp','Navigation.cpp','WalkerEvent.cpp']:
 p=root/name
 if not (backup/name).exists():shutil.copy2(p,backup/name)
p=root/'WalkerManager.h';s=p.read_text().replace('        WalkerState state;', '        WalkerState state;\n        bool explicit_target { false };')
s=s.replace('    bool SetWalkerNextPoint(ActorId id);', '    bool SetWalkerNextPoint(ActorId id);\n    bool HasExplicitTarget(ActorId id) const { auto it=_walkers.find(id);return it!=_walkers.end() && it->second.explicit_target; }')
p.write_text(s)
p=root/'WalkerManager.cpp';s=p.read_text().replace('if (dist.SquaredLength() <= 1)', 'if (dist.SquaredLength() <= (info.explicit_target && info.currentIndex+1==info.route.size() ? .01f : 1.f))')
s=s.replace('        return SetWalkerRoute(id, location);','''        const bool result=SetWalkerRoute(id, location);
        auto it=_walkers.find(id);if (it!=_walkers.end()) it->second.explicit_target=false;
        return result;''',1)
s=s.replace('        info.to = to;', '        info.to = to;\n        info.explicit_target = true;',1)
s=s.replace('            // we need a new route from here\n            SetWalkerRoute(id);', '            // Explicit destinations remain fixed until a client changes them.\n            if (!info.explicit_target) SetWalkerRoute(id);')
s=s.replace('                            SetWalkerRoute(it.first);', '                            if (!info.explicit_target) SetWalkerRoute(it.first);\n                            else { info.state=WALKER_STOP;_nav->PauseAgent(it.first,true); }')
p.write_text(s)
p=root/'Navigation.cpp';s=p.read_text().replace('          if (reset_target_pos) {','          if (reset_target_pos && !_walker_manager.HasExplicitTarget(_mapped_by_index[i])) {',1);p.write_text(s)
p=root/'WalkerEvent.cpp';s=p.read_text().replace('                auto state = event.actor->GetState();', '''                const auto movements = event.actor->GetMovementStates();
                if (movements & 0x8000) {
                    // The native circular fallback is red during movement control.
                    // Wait while this crossing's approach has an active movement.
                    for (int i=0;i<3;++i) {
                        const auto indication=(movements>>(3*i))&7;
                        if (indication==1 || indication==2 || indication==3) return EventResult::Continue;
                    }
                }
                auto state = event.actor->GetState();''');p.write_text(s)
