import taichi as ti
ti.init(ti.gpu)

n = 128
dt = 1e-3
substep = int(1 / 60 // dt)
quad_size = 1.0 / n
d = 1e2
g = ti.Vector([0, -9.8, 0])
spring_y = 1e3
spring_offsets = ti.Vector.field(2, dtype = int, shape = 6)
spring = ti.types.struct(a = int, b = int, c = int, d = int, e = float)
s = spring.field()
block = ti.root.dense(ti.i, 1)
index = block.dynamic(ti.j, n * n)
index.place(s)
p = ti.Vector.field(3, dtype = float, shape = (n, n))
v = ti.Vector.field(3, dtype = float, shape = (n, n))
f = ti.Vector.field(3, dtype = float, shape = (n, n))
indices = ti.field(dtype = int, shape = (n - 1) * (n - 1) * 6)
vertices = ti.Vector.field(3, dtype = float, shape = n * n)
colors = ti.Vector.field(3, dtype = float, shape = n * n)

ball_r = 0.3
ball_p = ti.Vector.field(3, dtype = float, shape = 1)
ball_p[0] = [0, 0, 0]

@ti.kernel
def init_cloth():
    #physical
    spring_offsets[0] = (0, 2)
    spring_offsets[1] = (0, 1)
    spring_offsets[2] = (1, 1)
    spring_offsets[3] = (2, 0)
    spring_offsets[4] = (1, 0)
    spring_offsets[5] = (1,-1)
    for i, j in ti.ndrange(n, n):
        for k in range(6):
            ni = i + spring_offsets[k][0]
            nj = j + spring_offsets[k][1]
            if 0 <= ni < n and 0<= nj < n:
                s[0].append(spring(i, j, ni, nj, ti.math.length(p[ni, nj] - p[i, j])))
    #rendering
    for i, j in ti.ndrange(n - 1, n - 1):
        quad_id = i * (n - 1) + j
        indices[quad_id * 6 + 0] = i * n + j
        indices[quad_id * 6 + 1] = (i + 1) * n + j
        indices[quad_id * 6 + 2] = i * n + (j + 1)
        indices[quad_id * 6 + 3] = (i + 1) * n + j + 1
        indices[quad_id * 6 + 4] = i * n + (j + 1)
        indices[quad_id * 6 + 5] = (i + 1) * n + j
    for i, j in ti.ndrange(n, n):
        if (i // 4 + j // 4) % 2 == 0:
            colors[i * n + j] = (0.46, 0.84, 0.92)
        else:
            colors[i * n + j] = (1, 1, 1)

@ti.kernel
def start():
    offset = ti.Vector([ti.random() - 0.5, 0, ti.random() - 0.5])
    for i,j in ti.ndrange(n, n):
        p[i, j] = [i * quad_size - 0.5, 0.6, j * quad_size - 0.5] + offset
        v[i, j] = [0, 0, 0]
        f[i, j] = g
        vertices[i * n + j] = p[i, j]

@ti.kernel
def update():
    for i,j in ti.ndrange(n, n):
        f[i, j] = g
        #v[i, j] *= 0.995
    for i in range(s[0].length()):
        x = s[0, i].a
        y = s[0, i].b
        nx = s[0, i].c
        ny = s[0, i].d
        dist_original = s[0, i].e
        dist_current = ti.math.length(p[nx, ny] - p[x, y])
        v_relative = (p[nx, ny] - p[x, y]).normalized().dot(v[x, y]) + (p[x, y] - p[nx, ny]).normalized().dot(v[nx, ny])
        force = spring_y * (dist_current / dist_original - 1)
        force -= d * v_relative
        
        f[x, y] += force * (p[nx, ny] - p[x, y]).normalized()
        f[nx, ny] += force * (p[x, y] - p[nx, ny]).normalized()
    for i,j in ti.ndrange(n, n):
        v[i, j] += dt * f[i, j]
        p[i, j] += dt * v[i, j]
        offset_to_center = p[i ,j] - ball_p[0]
        if ti.math.length(offset_to_center) <= ball_r:
            normal = offset_to_center.normalized()
            v[i, j] -= normal * min(v[i, j].dot(normal), 0)
            p[i, j] = ball_p[0] + ball_r * normal
        vertices[i * n + j] = p[i, j]

window = ti.ui.Window("Cloth Simulation", (1024, 1024), vsync = True)
canvas = window.get_canvas()
canvas.set_background_color((0, 0, 0))
scene = ti.ui.Scene()
camera = ti.ui.make_camera()
camera.position(0, 0, 3)
camera.lookat(0, 0, 0)
scene.set_camera(camera)
t = 0.0
start()
init_cloth()

while window.running:
    if t >= 1.5 :
        t = 0
        start()
    for i in range(substep):
        t += dt
        update()
    scene.point_light(pos = (0, 1, 2), color = (1, 1, 1))
    scene.mesh(vertices, indices = indices, per_vertex_color = colors, two_sided = True)
    scene.particles(ball_p, radius = ball_r, color = (0.3, 0.2, 0.5))
    canvas.scene(scene)
    window.show()