/* 晶体：全场唯一按全分辨率、连续着色的东西。
   形是截角八面体（6 个正方面 + 8 个六边形面），网格只用来盖住屏幕上的那一块；
   着色时每个像素在局部空间里与 14 个半空间求交，沿折射光线找出射面（至多四次体内全反射），
   RGB 三个通道各用一个折射率，出射后取像素化之后的画面——透过它看到的是被折弯的像素世界。 */
import * as THREE from 'three';
import { ConvexGeometry } from 'three/addons/geometries/ConvexGeometry.js';
import { shared } from './materials';

/** 截角八面体顶点 (0, ±1, ±2) 的全部排列，乘以 s */
function truncOctPoints(s: number) {
  const pts: THREE.Vector3[] = [];
  const axes = [
    [0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0],
  ];
  for (const [i0, i1, i2] of axes) {
    for (const a of [-1, 1]) {
      for (const b of [-2, 2]) {
        const v = [0, 0, 0];
        v[i0] = 0;
        v[i1] = a;
        v[i2] = b;
        pts.push(new THREE.Vector3(v[0] * s, v[1] * s, v[2] * s));
      }
    }
  }
  return pts;
}

const FRAG = /* glsl */ `
precision highp float;
uniform mat4 uInvModel, uModel, uVP;
uniform sampler2D tPix;
uniform float uS;
uniform vec3 uSun;
in vec3 vLocal;
out vec4 fragColor;

const float A = 0.5773502692;
const vec3 PN[14] = vec3[14](
  vec3(1, 0, 0), vec3(-1, 0, 0), vec3(0, 1, 0), vec3(0, -1, 0), vec3(0, 0, 1), vec3(0, 0, -1),
  vec3(A, A, A), vec3(A, A, -A), vec3(A, -A, A), vec3(A, -A, -A),
  vec3(-A, A, A), vec3(-A, A, -A), vec3(-A, -A, A), vec3(-A, -A, -A));
float hOf(int i) { return i < 6 ? 2.0 * uS : 1.7320508 * uS; }

const vec3 HORIZON = vec3(0.925, 0.867, 0.902);
const vec3 ZENITH = vec3(0.718, 0.753, 0.886);

bool enterHull(vec3 ro, vec3 rd, out float t, out int fi) {
  float tn = -1e9, tf = 1e9;
  fi = 0;
  for (int i = 0; i < 14; i++) {
    float dn = dot(PN[i], rd);
    float dist = hOf(i) - dot(PN[i], ro);
    if (abs(dn) < 1e-6) { if (dist < 0.0) return false; continue; }
    float ti = dist / dn;
    if (dn < 0.0) { if (ti > tn) { tn = ti; fi = i; } }
    else tf = min(tf, ti);
  }
  t = tn;
  return tn <= tf && tf > 0.0;
}

int exitFace(vec3 p, vec3 d, out float t) {
  t = 1e9;
  int fi = 0;
  for (int i = 0; i < 14; i++) {
    float dn = dot(PN[i], d);
    if (dn > 1e-6) {
      float ti = (hOf(i) - dot(PN[i], p)) / dn;
      if (ti < t) { t = ti; fi = i; }
    }
  }
  t = max(t, 0.0);
  return fi;
}

vec3 env(vec3 dw) {
  vec3 c = mix(HORIZON, ZENITH, smoothstep(-0.05, 0.7, dw.y));
  return c + vec3(1.0, 0.95, 0.92) * pow(max(dot(dw, uSun), 0.0), 120.0) * 1.4;
}

vec3 sampleBg(vec3 pL, vec3 dL) {
  vec3 pw = (uModel * vec4(pL, 1.0)).xyz;
  vec3 dw = normalize(mat3(uModel) * dL);
  vec4 c = uVP * vec4(pw + dw * 2.2, 1.0);
  if (c.w <= 0.05) return env(dw);
  vec2 uv = c.xy / c.w * 0.5 + 0.5;
  vec3 bg = texture(tPix, clamp(uv, 0.002, 0.998)).rgb;
  // 折到屏幕外的光换成天
  float out_ = max(max(-uv.x, uv.x - 1.0), max(-uv.y, uv.y - 1.0));
  return mix(bg, env(dw), smoothstep(0.0, 0.1, out_));
}

vec3 traceCh(vec3 p, vec3 d, float ior, out float len, out float glow) {
  len = 0.0;
  glow = 0.0;
  for (int k = 0; k < 5; k++) {
    float t;
    int fi = exitFace(p, d, t);
    float tc = clamp(-dot(p, d), 0.0, t);
    vec3 c = p + d * tc;
    glow += exp(-dot(c, c) / (uS * uS * 0.5)) * min(t / uS, 2.0);
    p += d * t;
    len += t;
    vec3 n = PN[fi];
    vec3 o = refract(d, -n, ior);
    if (dot(o, o) > 0.0) return sampleBg(p, o);
    if (k == 4) return sampleBg(p, d);
    d = reflect(d, -n);
  }
  return vec3(0.0);
}

void main() {
  vec3 ro = (uInvModel * vec4(cameraPosition, 1.0)).xyz;
  vec3 rd = normalize(vLocal - ro);
  float t;
  int fi;
  if (!enterHull(ro, rd, t, fi)) discard;
  vec3 p = ro + rd * t;
  vec3 n = PN[fi];

  float cosi = clamp(dot(-rd, n), 0.0, 1.0);
  float F = 0.05 + 0.95 * pow(1.0 - cosi, 5.0);

  float l0, l1, l2, g0, g1, g2;
  vec3 cr = traceCh(p, refract(rd, n, 1.0 / 1.48), 1.48, l0, g0);
  vec3 cg = traceCh(p, refract(rd, n, 1.0 / 1.50), 1.50, l1, g1);
  vec3 cb = traceCh(p, refract(rd, n, 1.0 / 1.525), 1.525, l2, g2);
  vec3 refr = vec3(cr.r, cg.g, cb.b);
  // 折进来的颜色收一点饱和度，色散只在细处露出来
  refr = mix(vec3(dot(refr, vec3(0.3, 0.55, 0.15))), refr, 0.7);
  float len = (l0 + l1 + l2) / 3.0 / uS;
  refr *= exp(-vec3(0.03, 0.065, 0.025) * len);
  vec3 glow = vec3(1.0, 0.9, 0.96) * (g0 + g1 + g2) / 3.0 * 0.09;

  vec3 nw = normalize(mat3(uModel) * n);
  vec3 rdw = normalize(mat3(uModel) * rd);
  vec3 col = refr * (1.0 - F) + env(reflect(rdw, nw)) * F + glow;

  // 棱：入射点离第二近的面有多远，一像素宽的亮线
  float m2 = -1e9;
  for (int i = 0; i < 14; i++) {
    if (i == fi) continue;
    m2 = max(m2, dot(PN[i], p) - hOf(i));
  }
  float w = fwidth(m2) * 1.3;
  col = mix(col, vec3(1.0, 0.99, 1.0), (1.0 - smoothstep(0.0, w, -m2)) * 0.6);

  fragColor = vec4(col, 1.0);
}
`;

export function makeCrystal(s = 0.32) {
  const geo = new ConvexGeometry(truncOctPoints(s));
  // 包围网格稍放大，避免光栅化的边比解析的边先被裁掉
  geo.scale(1.02, 1.02, 1.02);
  const mat = new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: {
      uInvModel: { value: new THREE.Matrix4() },
      uModel: { value: new THREE.Matrix4() },
      uVP: { value: new THREE.Matrix4() },
      tPix: { value: null },
      uS: { value: s },
      uSun: shared.uSun,
    },
    vertexShader: /* glsl */ `
out vec3 vLocal;
void main() {
  vLocal = position;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`,
    fragmentShader: FRAG,
  });
  const mesh = new THREE.Mesh(geo, mat);
  /** 外接球半径 */
  const radius = Math.sqrt(5) * s;

  function update(camera: THREE.Camera, pix: THREE.Texture) {
    mesh.updateMatrixWorld();
    mat.uniforms.uModel.value.copy(mesh.matrixWorld);
    mat.uniforms.uInvModel.value.copy(mesh.matrixWorld).invert();
    mat.uniforms.uVP.value.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    mat.uniforms.tPix.value = pix;
  }

  return { mesh, radius, update };
}
