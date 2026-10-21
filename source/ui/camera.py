"""Bounded map-grabbing camera helpers; no simulation state is changed."""
def clamp(renderer, engine):
    viewport, scale, origin = renderer.geometry(engine)
    extent = engine.config.size*scale
    for axis, available in enumerate((viewport.w, viewport.h)):
        desired = (available-extent)/2 if extent <= available else min(0, max(available-extent, origin[axis]))
        renderer.offset[axis] += desired-origin[axis]

def pan(renderer, engine, delta):
    renderer.offset[0] += delta[0]
    renderer.offset[1] += delta[1]
    clamp(renderer, engine)

def zoom_at(renderer, engine, factor, cursor):
    viewport, scale, origin = renderer.geometry(engine)
    if not viewport.collidepoint(cursor):
        return
    world = ((cursor[0]-origin[0])/scale, (cursor[1]-origin[1])/scale)
    renderer.zoom = min(16, max(1, renderer.zoom*factor))
    _, new_scale, new_origin = renderer.geometry(engine)
    renderer.offset[0] += cursor[0]-world[0]*new_scale-new_origin[0]
    renderer.offset[1] += cursor[1]-world[1]*new_scale-new_origin[1]
    clamp(renderer, engine)
