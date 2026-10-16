/* 物品的定义：带效果的实物。一件物品一个模块（src/items/<名字>.ts），在这里登记。
   场景里只标「在哪、怎么得到」（nx_type=item，见 docs/blender.md）；样子、效果、得到时的演出都在模块里。
   效果目前只改「自己」：拿在手里的东西、看到的东西、移动与视角。
   模型一律以米为单位，用世界的材质（会动的用 materials.ts 的 charm），由管线统一像素化、落色板、描边。 */
import type * as THREE from 'three';
import type { L } from '../i18n';
import type { Exit } from '../mapview';
import { nightPiece } from './night';

export interface ItemCtx {
  world: string;
  feet: THREE.Vector3;
  /** 眼睛在哪（一片夜朝着人，星按「从人看过去」摆） */
  eye: THREE.Vector3;
  camera: THREE.PerspectiveCamera;
  t: number;
  /** 本世界的出入口（一片夜里的小星按它摆） */
  exits: Exit[];
  /** 地图开着（一片夜碎开了、等着合回来） */
  mapOpen: boolean;
}

/** 一个摆出来的样子：模型，加上每帧的动画（可选） */
export interface Shown {
  object: THREE.Object3D;
  update?(dt: number, ctx: ItemCtx): void;
}

/** 拿在手里：画在手边（画面右下），按住 Q 时举起来、使用。怎么用（捏、按、转……）由各件自己的动作表现 */
export interface HeldModel {
  object: THREE.Object3D;
  /** press：用到了几成 0..1（按住 Q 时往 1 走）。返回 true ＝ 这一帧用到了底 */
  update(dt: number, press: number, ctx: ItemCtx): boolean;
}

export interface ItemDef {
  id: string;
  name: L;
  /** 日记「拾得」页上的说明 */
  desc: L;
  /** need 必要的（好拿）· collect 收藏品（藏得深、条件难） */
  kind: 'need' | 'collect';
  /** 像素画：得到时的卡片、日记都用它；没写 world() 时也是世界里的纸片（每米 16 像素） */
  icon(): HTMLCanvasElement;
  /** 在世界里、环绕展示时的样子：原点在底面中心。没写就是一张浮着、正面朝人的纸片 */
  world?(): Shown;
  /** nx_get=custom 时：条件满足就得到 */
  check?(ctx: ItemCtx): boolean;
  /** 拿在手里的样子与使用时的动作（原点在装置的中心） */
  held(): HeldModel;
  /** 用到底时发生的事（没写就只有模型自己的反应） */
  bloom?(): void;
}

export const ITEMS: ItemDef[] = [nightPiece];

export const itemDef = (id: string) => ITEMS.find((d) => d.id === id);
