"""Per-class serializers, transcribed from CTStageEditorPCMMaster64.exe (PCM 26).

Each function mirrors one class's virtual Load(stream) method in the Stage
Editor. `io.av` is the archive version, `io.ver` the per-object class version
and `io.flag` the archive flag. The comment on each function gives the RVA of
the Load method it was transcribed from.

Field names are descriptive where the meaning is clear from the data or the
code. Others keep the member offset inside the C++ object (e.g. `f_0x124`) so
they can be traced back to the executable.
"""
CLASSES = {}
NO_HEADER = set()   # classes whose Load does not call CTBaseObject::Load


def cls(*names):
    def deco(fn):
        for n in names:
            CLASSES[n] = fn
        return fn
    return deco


# ------------------------------------------------------------------ stage
@cls('CTStage')
def stage(io):  # 0x46b200
    for k in ('landscape', 'route', 'road_network', 'river_network', 'water_network', 'vegetation',
              'audience', 'road_border_manager', 'cities', 'road_spline', 'spawnable_object_manager',
              'circuit_manager', 'podium', 'sprint_manager', 'monument_manager',
              'audio_commentary_manager', 'spline_description_manager', 'profile_camera_manager'):
        io.ref(k)
    if io.av > 0x3c: io.ref('electric_network')
    if io.av > 0x41: io.ref('fence_network')
    if io.av > 0x45:
        io.vec3('f_0x1d8'); io.str('f_0x1e8')
        io.vec3('f_0x210'); io.str('f_0x220')
    io.u32('f_0x168')
    if io.av >= 0x49: io.ref('stage_info')
    if io.av >= 0x82: io.u8('f_0x16c')
    if io.av > 0x51:
        io.ref('wall_house_network')
        io.ref('spline_spawnable_network')


@cls('CTStageInfo')
def stage_info(io):  # 0x4a1c80
    io.str('name'); io.str('region')
    io.i32('region_id')            # ver < 3: old id (0x14 is remapped to -1 by the engine)
    io.i32('f_0x70')
    if io.ver >= 1:
        io.f32('f_0x80'); io.f32('f_0x84'); io.u8('f_0x8c'); io.u32('f_0x88'); io.u32('f_0x90')
    if io.ver >= 2:
        io.i32('f_0x68'); io.f32('f_0x74'); io.i32('f_0x78'); io.f32('f_0x7c')


# ------------------------------------------------------------------ landscape
@cls('CTLandscape')
def landscape(io):  # 0x426da0
    io.ivec2('gps_min'); io.ivec2('gps_max')      # (longitude, latitude) in 1e-7 degrees
    io.f32('size')
    io.ref('root_tree')
    if io.av >= 0x73: io.f32('global_0x00c03b20')


def height_map(io, elem_fmt):
    """CTAbstractLandscapeTreeMap<T>::Load (0x4911a0 / 0x490ea0)."""
    io.u16('resolution')
    io.ivec2('gps_min'); io.ivec2('gps_max')
    io.vec2('min'); io.vec2('max')
    n = io.count('values', 'H')
    io.array('values', elem_fmt, n)


def height_data(io):  # CTHeightData::Load 0x4243e0
    io.u16('resolution')
    io.f32('min_height'); io.f32('max_height')
    io.list('quadrant_heights', lambda io: (io.f32('min'), io.f32('max')), count=4)
    io.f32('height_offset')                             # height_m = sample * 0.1 + height_offset
    flag = io.u8('heightmap_only')
    io.sub('height_map', lambda io: height_map(io, 'H'))          # CTHeightMap: u16 samples, 0.1 m steps
    if not flag:
        io.sub('terraform_map', lambda io: height_map(io, 'I'))   # CTTerraformMap (4-byte CTTerraformData)


@cls('CTLandscapeTree')
def landscape_tree(io):  # 0x432100
    io.ref('parent'); io.ref('landscape')
    io.u32('level')
    io.vec2('min'); io.vec2('max')
    io.u32('f_0x148')
    for i in range(4): io.ref(f'child{i}')
    io.sub('height_data', height_data)
    for i in range(4): io.vlist(f'neighbours{i}', 'ref')
    if io.u8('has_geometry'):
        io.raw('uv_map', 0x8408)                                    # CTLandscapeGeometry -> CTUVMap (0x484700)
    for i in range(4): io.ref(f'f_0x150_{i}')
    io.vlist('f_0x13b8', 'ref')


# ------------------------------------------------------------------ route
@cls('CTRoute')
def route(io):  # 0x460b70
    io.ref('route_descriptor')
    if io.av >= 0x3b:
        io.u8('f_0x7a'); io.vec2('f_0x7c')


@cls('CTRouteDescriptor')
def route_descriptor(io):  # 0x460270
    io.vlist('points', 'ref')


# ------------------------------------------------------------------ generic cubic bezier splines
def spline_network(io):  # CTCubicBezierSplineNetwork::Load 0x5ee610
    io.vlist('splines', 'ref')
    io.vlist('control_points', 'ref')
    io.vlist('intersections', 'ref')


def spline(io):  # CTCubicBezierSpline::Load 0x5e7e20
    io.u8('f_0x28')
    io.f32('length'); io.f32('f_0x84')
    io.vec2('bbox_min'); io.vec2('bbox_max')
    io.ref('network'); io.ref('first_curve'); io.ref('last_curve')


def curve(io):  # CTCubicBezierCurve::Load 0x5e01b0
    io.u8('f_0x28')
    io.ref('start_point'); io.ref('end_point')
    io.ref('start_tangent'); io.ref('end_tangent')
    io.ref('prev_curve'); io.ref('next_curve')
    io.ref('spline')
    io.f32('length')
    io.vec3('bbox_min'); io.vec3('bbox_max')
    io.u32('f_0x124')
    io.ref('loose_grid')
    if io.ver >= 1:
        io.u8('f_0xa0'); io.u8('f_0xa1')


def main_control_point(io):  # CTCubicBezierMainControlPoint::Load 0x5e4c60
    io.vec3('position'); io.vec3('f_0x3c')
    io.vlist('curves', 'ref')
    io.ref('intersection')
    io.vec2('f_0xd0')


@cls('CTCubicBezierTangentControlPoint', 'CTRoadTangentControlPoint', 'CTWaterTangentControlPoint')
def tangent_control_point(io):  # 0x5f0700
    io.vec3('position'); io.vec3('f_0x3c'); io.vec3('f_0xb0')
    io.ref('curve')


@cls('CTCubicBezierCurveLooseGrid', 'CTAudience', 'CTVegetationObjectManager')
def nothing(io):  # 0x509760: CTBaseObject::Load only
    pass


CLASSES.update({
    'CTCubicBezierCurve': curve,
    'CTElectricCurve': curve, 'CTRiverCurve': curve, 'CTSplineSpawnableCurve': curve,
    'CTWallHouseCurve': curve, 'CTWaterCurve': curve,
    'CTElectricNetwork': spline_network, 'CTFenceNetwork': spline_network, 'CTFieldAreaManager': spline_network,
    'CTForestAreaManager': spline_network, 'CTRiverNetwork': spline_network,
    'CTSplineSpawnableNetwork': spline_network, 'CTTreesRowManager': spline_network,
    'CTWallHouseNetwork': spline_network, 'CTWaterNetwork': spline_network,
    'CTCityAreaPoint': main_control_point, 'CTElectricPoint': main_control_point,
    'CTFencePoint': main_control_point, 'CTFieldAreaPoint': main_control_point,
    'CTForestAreaPoint': main_control_point, 'CTRiverPoint': main_control_point,
    'CTSplineSpawnablePoint': main_control_point, 'CTWallHousePoint': main_control_point,
})


# ------------------------------------------------------------------ roads
@cls('CTRoadNetwork')
def road_network(io):  # 0x3c6930
    spline_network(io)
    if io.ver >= 1: io.ref('section_manager')


@cls('CTRoad')
def road(io):  # 0x37cd40
    spline(io)
    io.ref('bridges_and_tunnels')


@cls('CTRoadCurve')
def road_curve(io):  # 0x37bd80
    curve(io)
    if io.av > 0x35: io.u32('f_0x234')
    io.str('road_start'); io.str('road_end'); io.str('mark_start'); io.str('mark_end')
    io.u32('f_0x228'); io.u8('f_0x230'); io.str('template')
    io.u32('f_0x244'); io.u8('f_0x238'); io.u8('f_0x239'); io.f32('f_0x23c'); io.f32('f_0x240')
    if io.av > 0x46: io.str('color_start'); io.str('color_end')
    if io.av > 0x69: io.u8('f_0x231')


@cls('CTRoadPoint', 'CTMonumentRoadPoint')
def road_point(io):  # 0x3d66e0
    main_control_point(io)
    if io.ver >= 1: io.str('name')


def spline_intersection(io):  # CTCubicBezierSplineIntersection::Load 0x5ebc90
    io.u8('f_0x28')
    io.vec3('position')                                   # (av > 0x31)
    io.vec2('bbox_min'); io.vec2('bbox_max')
    io.ref('point')
    io.vlist('corners', 'vec3')
    io.ctable('positions', 'fffff')                       # CTIntersectionPositions (0x5eb510)
    if io.ver >= 1: io.u8('f_0xdc')


@cls('CTRoadIntersection')
def road_intersection(io):  # 0x3acbf0
    spline_intersection(io)
    io.str('road')
    if io.av > 0x3b:
        io.u8('f_0x1e8')
        io.u32('f_0x11c'); io.f32('f_0x120')
        if io.av > 0x44: io.str('preset')


@cls('CTBridgesAndTunnelsManager')
def bridges_and_tunnels(io):  # 0x3fc7f0
    io.ref('road')
    io.list('items', lambda io: (io.ref('curve'), io.str('model'), io.f32('start'), io.f32('end')))


def _section(io):
    io.str('name'); io.u32('type'); io.f32('start'); io.f32('end')


@cls('CTSectionManager')
def section_manager(io):  # 0x3f6240
    if io.ver == 0:
        io.raw('legacy', 0x30)
        return
    io.list('sections', _section)
    if io.ver >= 2:
        io.list('sections2', _section)


@cls('CTRoadSpline')
def road_spline(io):  # 0x5217d0
    if io.av > 0x37: io.ref('city_spline_heightmap')
    if io.flag == 1 and io.av >= 0x68: io.ref('road_best_traj')


@cls('CTCitySplineHeightMap')
def city_spline_heightmap(io):  # 0x5948e0 (no base header)
    if not (io.av > 0x37 and io.flag == 1):
        return

    def item(io):
        io.f32('start'); io.f32('end')
        n = io.count('profiles')
        io.f32('f_0x28'); io.f32('f_0x2c')
        io.list('profiles', lambda io: (io.vlist('left', 'f32'), io.vlist('right', 'f32')), count=n)
    io.list('items', item)


NO_HEADER.add('CTCitySplineHeightMap')


@cls('RoadBestTraj')
def road_best_traj(io):  # 0x52e270
    if io.u32('traj_version') != 0x69:
        return  # the engine stops reading here ("Bad traj version ... need to be regen")
    n = io.count('samples')
    # per sample: 4 x (f_0x98[k], f_0x38[k]) pairs, then f_0xf8 and f_0x140
    io.rows('samples', 'f', 10, n)


@cls('CTRoadBorderData')
def road_border_data(io):  # 0x64d5f0
    io.f32('f_0x40')


@cls('CTRoadBorderManager')
def road_border_manager(io):  # 0x653f40
    io.u32('f_0x24'); io.f32('f_0x28'); io.f32('f_0x2c')
    io.ref('road_border_data')
    if io.av > 0x43:
        if io.u8('has_modifier'):                         # CTRoadBorderModifier (0x65db10)
            io.ctable('modifier', 'fff')
    if io.ver >= 1: io.vlist('f_0x98', 'str')
    if io.ver >= 2: io.u8('f_0xb0')


# ------------------------------------------------------------------ fences / vegetation
@cls('CTFenceSpline')
def fence_spline(io):  # 0x53f4b0
    spline(io)
    io.str('preset'); io.str('wall'); io.str('pillar'); io.str('gate')
    if io.av > 0x40: io.u8('f_0x188')
    if io.ver >= 1: io.u32('f_0x18c')


@cls('CTFenceCurve')
def fence_curve(io):  # 0x53f890
    curve(io)
    io.u8('f_0x150'); io.f32('f_0x154')


@cls('CTVegetation')
def vegetation(io):  # 0x507720
    io.ref('field_area_manager'); io.ref('forest_area_manager'); io.ref('trees_row_manager')
    io.ref('vegetation_object_manager')
    for k in ('f_0x58', 'f_0x5c', 'f_0x60', 'f_0x64', 'f_0x68'): io.u32(k)


@cls('CTFieldArea')
def field_area(io):  # 0x4de230
    spline(io)
    for k in ('f_0x138', 'f_0x140', 'f_0x144', 'f_0x148', 'f_0x14c'): io.u32(k)
    io.array('f_0x150', 'f', 5)
    io.u32('f_0x13c')


@cls('CTForestArea')
def forest_area(io):  # 0x4ef290
    spline(io)
    for k in ('f_0x104', 'f_0x108', 'f_0x10c', 'f_0x110'): io.u32(k)
    io.array('f_0x114', 'f', 7)
    io.u32('f_0x130'); io.u32('f_0x134')


# ------------------------------------------------------------------ objects, podium, sprints
@cls('CTSpawnableObjectManager')
def spawnable_object_manager(io):  # 0x6051f0
    io.vlist('objects', 'ref')


@cls('CTSpawnedObject')
def spawned_object(io):  # 0x60f6f0
    io.vec3('position'); io.vec3('f_0x3c_a'); io.vec3('f_0x3c_b')
    io.str('model')
    if io.av >= 0x40: io.vec4('f_0x148')
    if io.ver >= 1: io.u8('f_0x158')


@cls('CTCircuitManager')
def circuit_manager(io):  # 0x5dd1d0
    io.vlist('circuits', 'ref')


@cls('CTCircuit')
def circuit(io):  # 0x5dcb70
    io.str('name'); io.u32('laps')
    io.vlist('points', 'ref')


@cls('CTPodium')
def podium(io):  # 0x635190
    if io.av > 0x33: io.u8('f_0x28')
    io.vec3('position'); io.vec3('rotation')
    io.str('model')
    if io.ver >= 1: io.u8('f_0x1a0')


@cls('CTSprintManager')
def sprint_manager(io):  # 0x4a7420
    io.vlist('sprints', 'ref')


@cls('CTSprint')
def sprint(io):  # 0x4a5cd0
    io.str('name'); io.str('city')
    io.f32('position')
    io.u32('type')
    io.vlist('linked_sprints', 'ref')
    io.list('f_0x1e8', lambda io: (io.f32('position'), io.u8('flag')))
    if io.av > 0x68: io.f32('f_0x250'); io.f32('f_0x254')
    if io.av >= 0x72: io.u8('f_0x258')
    if io.av > 0x87:
        io.u8('f_0x84'); io.u32('f_0x88'); io.u32('f_0x8c'); io.u32('f_0x90')


@cls('CTMonumentManager')
def monument_manager(io):  # 0x6786f0
    io.vlist('monuments', 'ref')


@cls('CTMonument')
def monument(io):  # 0x673df0
    io.u8('f_0x28'); io.u32('type'); io.u32('f_0x70')
    if io.av >= 0x35: io.u32('f_0x74')
    io.vec3('position'); io.f32('f_0x84')
    if io.av >= 0x87:
        io.vlist('road_points', 'ref')
    else:
        io.ref('road_point_a'); io.ref('road_point_b')


@cls('CTAudioCommentaryManager')
def audio_commentary_manager(io):  # 0x62bd40
    io.vlist('commentaries', 'ref')


@cls('CTAudioCommentary')
def audio_commentary(io):  # 0x62ba80
    io.str('sound'); io.f32('position')


@cls('CTSplineDescriptionManager')
def spline_description_manager(io):  # 0x66f090
    io.vlist('descriptions', 'ref')


@cls('CTSplineDescription')
def spline_description(io):  # 0x66ec80
    if io.av >= 0x65: io.u32('f_0x24')
    io.str('name')
    for k in ('f_0x48', 'f_0x4c', 'f_0x50', 'f_0x58', 'f_0x54'): io.f32(k)


@cls('CTProfileCameraManager')
def profile_camera_manager(io):  # 0x62d380
    io.vlist('cameras', 'ref')


@cls('CTProfileCamera')
def profile_camera(io):  # 0x62d310
    for k in ('f_0x24', 'f_0x28', 'f_0x2c', 'f_0x30'): io.f32(k)


# ------------------------------------------------------------------ houses / spawnables along splines
@cls('CTWallHouseSpline')
def wall_house_spline(io):  # 0x4bc000
    spline(io)
    io.str('preset')
    io.f32('f_0x8058'); io.f32('f_0x805c'); io.f32('f_0x8060'); io.u32('f_0x8064')
    io.u8('f_0x8068')
    io.list('houses', lambda io: (io.str('model'), io.vec3('position'), io.vec3('rotation')))
    io.str('road'); io.str('sidewalk_texture')
    io.f32('f_0x8030'); io.u32('f_0x8034')
    io.str('wall_preset')
    io.f32('f_0x8090'); io.u32('f_0x8094')
    io.u8('f_0x8098'); io.u8('f_0x8099')
    if io.ver >= 1: io.u8('f_0x809a'); io.f32('f_0x80b8')
    if io.ver >= 2: io.u8('f_0x8069')
    if io.ver >= 3:
        io.u8('f_0x149'); io.str('village')
        io.vlist('fence_spline_indices', 'u32')
    if io.ver >= 4:
        io.u8('f_0x809b'); io.str('f_0x188_text')


@cls('CTSplineSpawnable')
def spline_spawnable(io):  # 0x63a430
    spline(io)
    io.list('presets', lambda io: (io.str('name'), io.u32('weight')))
    io.u8('f_0x118')
    io.f32('f_0x11c'); io.f32('f_0x120'); io.f32('f_0x124'); io.f32('f_0x128')
    io.u8('f_0xfa'); io.u8('f_0xfb')
    io.list('objects', lambda io: (io.str('model'), io.vec3('position'), io.vec3('rotation')))


@cls('CTElectricSpline')
def electric_spline(io):  # 0x67e440
    spline(io)


# ------------------------------------------------------------------ water
@cls('CTRiver')
def river(io):  # 0x5d37d0
    spline(io)
    io.str('type'); io.str('shore')
    io.u8('f_0x164')
    if io.av >= 0x83:
        io.u8('f_0x165'); io.f32('f_0x160')
    for k in ('f_0x1e0', 'f_0x1e4'): io.f32(k)
    io.vec3('f_0x174'); io.vec3('f_0x168')
    io.f32('f_0x180'); io.vec2('f_0x184')
    for k in ('f_0x190', 'f_0x194', 'f_0x19c', 'f_0x198', 'f_0x18c', 'f_0x1f8', 'f_0x1f0', 'f_0x1f4',
              'f_0x1e8', 'f_0x1ec'):
        io.f32(k)
    io.str('normal_map_a'); io.str('normal_map_b')


@cls('CTWater')
def water(io):  # 0x547120
    spline(io)
    io.str('type'); io.str('shore')
    for k in ('f_0x188', 'f_0x18c', 'f_0x270', 'f_0x274'): io.f32(k)
    io.vec3('f_0x1c0'); io.vec3('f_0x1dc')
    io.f32('f_0x1cc'); io.vec2('f_0x1d0')
    for k in ('f_0x21c', 'f_0x220', 'f_0x228', 'f_0x224', 'f_0x1d8', 'f_0x280', 'f_0x284', 'f_0x278', 'f_0x27c'):
        io.f32(k)
    io.str('normal_map_a'); io.str('normal_map_b')
    if io.av >= 0x3a: io.u8('f_0x195')
    if io.av >= 0x71: io.f32('f_0x14c')


@cls('CTWaterPoint')
def water_point(io):  # 0x5593b0
    main_control_point(io)
    if io.av >= 0x3a:
        io.u8('f_0xd9'); io.f32('f_0xdc')


# ------------------------------------------------------------------ cities
@cls('CTCities')
def cities(io):  # 0x57c400
    spline_network(io)
    if io.av >= 0x33: io.u32('city_mask')
    io.vlist('city_views', 'ref')


def ground_graph(io):  # 0x5c5f30
    nv = io.count('vertices'); ne = io.count('edges')
    io.rows('vertices', 'f', 3, nv)
    io.table('edges', 'IIf', ne)                      # (vertex a, vertex b, length)


@cls('CTCity')
def city(io):  # 0x5856e0
    spline(io)
    io.ref('terraformer'); io.ref('city_view')
    if io.marker('has_center', 0xffffffff): io.vec2('center')

    def a(io):  # this block's size covers the rest of the object
        io.ref('cities')
        io.vlist('parts', 'ref')
        io.sub('ground_graph', ground_graph)
        io.block(0x80007, lambda io: (io.u32('f_0x7ff8'), io.u32('f_0x7ffc')), 'block_80007')
        io.str('name')
        io.u32('city_type')
    io.block(0x70008, a, 'block_70008')


@cls('CTCityTerraformer')
def city_terraformer(io):  # 0x4808c0
    io.u8('f_0x28')


def mesh(io):  # CTCityView geometry block (0x6884c0)
    for k in ('positions', 'normals', 'tangents', 'binormals'):
        io.ctable(k, 'fff')                           # 0x68d3e0
    io.ctable('colors', 'ffff')
    io.ctable('uv0', 'ff'); io.ctable('uv1', 'ff')    # 0x68d450
    c = io.count('indices'); io.array('indices', 'I', c)


def geom_desc(io):  # 0x687e60
    io.u32('shader'); io.str('diffuse'); io.str('normal_map'); io.str('gloss')
    io.u32('options_mask'); io.vec4('color')


def _points_w(io, n):  # 0x597900 (av > 0x38: vec3 + u32 per item)
    io.ctable(n, 'fffI' if io.av > 0x38 else 'fff')


@cls('CTCityView')
def city_view(io):  # 0x5980c0
    if io.av > 0x36:
        io.u32('f_0x160c'); io.u32('f_0x1610'); io.u32('f_0x1614')
    if io.flag != 1:
        return
    # Fixed-size records. Integer columns hold handles of the form (kind << 24) | index.
    io.ctable('f_0x78', 'I' + 'f' * 13 + 'I' * 7)    # 0x54 bytes
    io.ctable('f_0x90', 'f' * 9 + 'I')               # 0x28 bytes
    io.ctable('f_0xa8', 'f' * 5 + 'I')               # 0x18 bytes
    io.ctable('f_0xc0', 'fII')                       # 0x0c bytes
    io.ctable('f_0xd8', 'I' + 'f' * 6 + 'I')         # 0x20 bytes
    io.ctable('f_0x1950', 'fff')                     # 0x5928e0
    io.u32('f_0x1948')
    m1 = io.marker('marker_ffffffff', 0xffffffff)
    m2 = io.marker('marker_fffffffe', 0xfffffffe)
    if m2: io.vec2('center')
    if m1 or m2:
        _points_w(io, 'f_0x19e8')
        io.ctable('f_0x19b8', 'fff')                 # 0x5c6290
    _points_w(io, 'f_0x19d0')
    if io.av < 0x48:
        raise NotImplementedError('CTCityView for archive version < 0x48')
    io.ctable('f_0x1a00', 'fffffIfff')               # 0x24 bytes
    io.sub('mesh_0x1618', mesh)
    io.sub('mesh_0x17b0', mesh)
    io.u32('reserved')                               # the engine asserts this is 0
    io.list('static_layers', lambda io: io.ctable('items', 'If'), count=4)   # CTCityViewStaticLayer
    io.list('geom_groups', lambda io: (io.sub('desc', geom_desc), io.sub('mesh', mesh)))


@cls('CTZone')
def zone(io):  # 0x5a7690
    io.ref('part')
    io.vlist('blocs', 'ref')
    io.u32('f_0x7c')
    for k in ('graph_0x80', 'graph_0xb8', 'graph_0xf0', 'graph_0x128'):
        io.sub(k, ground_graph)
    io.block(0x80007, lambda io: io.table('f_0x160', 'IIII', 1), 'block_80007')


@cls('CTPart')
def part(io):  # 0x5a0540
    io.ref('city')
    io.vlist('zones', 'ref')
    io.sub('ground_graph', ground_graph)
    io.block(0x80007, lambda io: io.table('f_0xb4', 'IfIII', 1), 'block_80007')


@cls('CTBloc')
def bloc(io):  # 0x56a860 (no base header)
    io.ref('zone')
    io.ctable('outline', 'fff')                      # 0x5928e0
    io.block(0x80008, lambda io: io.table('f_0xc8', 'I' * 11 + 'ffI', 1), 'block_80008')


NO_HEADER.add('CTBloc')
