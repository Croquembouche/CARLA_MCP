from pathlib import Path
import shutil
root=Path('/mnt/simulations/carla');backup=Path('/mnt/simulations/control-center/data/reliability-backup/native')
def edit(relative,fn):
 p=root/relative;q=backup/relative;q.parent.mkdir(parents=True,exist_ok=True)
 if not q.exists():shutil.copy2(p,q)
 p.write_text(fn(p.read_text()))
shader='Unreal/CarlaUnreal/Plugins/Carla/Shaders/Private/CarlaSensorTrace.usf'
def patch_shader(s):
 pos=s.index('[numthreads')
 s=s[:pos]+'''// Reject render-only primitives during traversal instead of restarting the ray.
// FORCE_NON_OPAQUE ensures even opaque geometry passes the collision predicate.
struct FCarlaCollisionCallback
{
    bool OnAnyHit(float3 Origin, float3 Direction, FTraceRayInlineResult Candidate)
    {
        FInstanceSceneData Instance = GetInstanceSceneData(Candidate.InstanceID, Scene.GPUScene.InstanceDataSOAStride);
        uint Component = GetPrimitiveData(Instance.PrimitiveId).PrimitiveComponentId;
        uint Actor = LookupActor(Component);
        return Actor != 0 && Actor != IgnoredActor;
    }
};

'''+s[pos:]
 pos=s.index('    // Render-only surfaces')
 return s[:pos]+'''    FCarlaCollisionCallback Filter;
    FTraceRayInlineResult Hit = TraceRayInlineWithCallback(TLAS, RAY_FLAG_FORCE_NON_OPAQUE,
        0xff, Ray, CreateTraceRayInlineContext(), Filter);
    if (!Hit.IsHit()) return;
    FInstanceSceneData Instance = GetInstanceSceneData(Hit.InstanceID, Scene.GPUScene.InstanceDataSOAStride);
    uint Component = GetPrimitiveData(Instance.PrimitiveId).PrimitiveComponentId;
    Hits[Index * 2] = float4(Hit.HitT, asfloat(Component), 0, 0);
    Hits[Index * 2 + 1] = float4(Hit.WorldGeometryNormal, 0);
}
'''
edit(shader,patch_shader)
# Public, read-only complete navigation query, with the same agent filter as locomotion.
edit('LibCarla/source/carla/nav/Navigation.h',lambda s:s.replace('    bool GetPath(','''    std::vector<carla::geom::Location> GetCompletePath(ActorId id,
        carla::geom::Location from, carla::geom::Location to);

    bool GetPath(''',1))
def nav(s):
 pos=s.index('  bool Navigation::GetPath(')
 return s[:pos]+'''  std::vector<carla::geom::Location> Navigation::GetCompletePath(ActorId id,
      carla::geom::Location from, carla::geom::Location to) {
    std::scoped_lock<std::mutex> lock(_mutex);
    if (!_ready || !_nav_query || !_crowd) return {};
    const dtQueryFilter *filter = _crowd->getFilter(0);
    const auto walker = _mapped_walkers_id.find(id);
    if (walker != _mapped_walkers_id.end())
      filter = _crowd->getFilter(_crowd->getAgent(walker->second)->params.queryFilterType);
    float ext[3] = {2.f,4.f,2.f};
    float start[3] = {from.x,from.z,from.y}, end[3] = {to.x,to.z,to.y};
    float projected_start[3], projected_end[3]; dtPolyRef a=0,b=0;
    if (dtStatusFailed(_nav_query->findNearestPoly(start,ext,filter,&a,projected_start)) ||
        dtStatusFailed(_nav_query->findNearestPoly(end,ext,filter,&b,projected_end)) || !a || !b) return {};
    dtPolyRef corridor[MAX_POLYS]; int count=0;
    auto status=_nav_query->findPath(a,b,projected_start,projected_end,filter,corridor,&count,MAX_POLYS);
    if (dtStatusFailed(status) || dtStatusDetail(status,DT_BUFFER_TOO_SMALL) ||
        dtStatusDetail(status,DT_OUT_OF_NODES) || !count || corridor[count-1]!=b) return {};
    float points[MAX_POLYS*3]; unsigned char flags[MAX_POLYS]; dtPolyRef refs[MAX_POLYS]; int n=0;
    status=_nav_query->findStraightPath(projected_start,projected_end,corridor,count,points,flags,refs,&n,MAX_POLYS,DT_STRAIGHTPATH_AREA_CROSSINGS);
    if (dtStatusFailed(status) || dtStatusDetail(status,DT_BUFFER_TOO_SMALL) || !n || !(flags[n-1]&DT_STRAIGHTPATH_END)) return {};
    std::vector<carla::geom::Location> result; result.reserve(n);
    for(int i=0;i<n;++i) result.emplace_back(points[3*i],points[3*i+2],points[3*i+1]);
    return result;
  }

'''+s[pos:]
edit('LibCarla/source/carla/nav/Navigation.cpp',nav)
edit('LibCarla/source/carla/client/detail/WalkerNavigation.h',lambda s:s.replace('    // set a new target point to go', '''    std::vector<geom::Location> GetCompletePath(ActorId id, geom::Location from, geom::Location to) {
      return _nav.GetCompletePath(id, from, to);
    }

    // set a new target point to go''',1))
edit('LibCarla/source/carla/client/WalkerAIController.h',lambda s:s.replace('    void GoToLocation(','''    std::vector<geom::Location> GetNavigationPath(const geom::Location &destination);

    void GoToLocation(''').replace('#include <optional>','#include <optional>\n#include <vector>'))
edit('LibCarla/source/carla/client/WalkerAIController.cpp',lambda s:s.replace('  void WalkerAIController::GoToLocation(','''  std::vector<geom::Location> WalkerAIController::GetNavigationPath(const geom::Location &destination) {
    auto walker=GetParent(); auto nav=GetEpisode().Lock()->GetNavigation();
    return walker && nav ? nav->GetCompletePath(walker->GetId(),walker->GetLocation(),destination) : std::vector<geom::Location>{};
  }

  void WalkerAIController::GoToLocation(''',1))
edit('PythonAPI/carla/src/Actor.cpp',lambda s:s.replace('    .def("go_to_location", &cc::WalkerAIController::GoToLocation', '''    .def("get_navigation_path", +[](cc::WalkerAIController &self, const cg::Location &destination) { return StdVectorToPyList(self.GetNavigationPath(destination)); }, (arg("destination")))
    .def("go_to_location", &cc::WalkerAIController::GoToLocation''',1))
# Stress the old 256-retrace limit with 300 ignored boxes (600 faces).
def selftest(s):
 s=s.replace('  auto* Target = SpawnCube(1000, true);','''  auto* Target = SpawnCube(1000, true);
  TArray<TWeakObjectPtr<AStaticMeshActor>> Layers;
  for (int32 I=0; I<300; ++I) {
    auto* Layer=SpawnCube(10+I*2,false);
    Layer->SetActorScale3D(FVector(.005,2,2)); Layers.Add(Layer);
  }''')
 s=s.replace('[World, Origin, WeakOwner, WeakTarget, WeakOccluder]', '[World, Origin, WeakOwner, WeakTarget, WeakOccluder, Layers]')
 s=s.replace('WeakOccluder, CpuMs, Submitted]', 'WeakOccluder, Layers, CpuMs, Submitted]')
 s=s.replace('      if (WeakTarget.IsValid()) WeakTarget->Destroy();','      for (auto& Layer : Layers) if (Layer.IsValid()) Layer->Destroy();\n      if (WeakTarget.IsValid()) WeakTarget->Destroy();')
 return s
edit('Unreal/CarlaUnreal/Plugins/Carla/Source/Carla/Sensor/GpuSensorSelfTest.cpp',selftest)
