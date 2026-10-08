/* 物品的定义：带效果的实物。一件物品一个模块（src/items/<名字>.ts），在这里登记。
   场景里只标「在哪、怎么得到」（nx_type=item，见 docs/blender.md）；样子、效果、得到时的演出都在模块里。
   效果目前只改「自己」：拿在手里的东西、看到的东西、移动与视角。
   模型一律以米为单位，用世界的材质（会动的用 materials.ts 的 charm），由管线统一像素化、落色板、描边。 */
import type * as THREE from 'three';
import { compass } from './compass';

export interface ItemCtx {
  world: string;
  feet: THREE.Vector3;
  t: number;
}

/** 一个摆出来的样子：模型，加上每帧的动画（可选） */
export interface Shown {
  object: THREE.Object3D;
  update?(dt: number, t: number): void;
}

/** 拿在手里：画在手边（画面右下），按住 Q 时举起来、捏紧 */
export interface HeldModel {
  object: THREE.Object3D;
  /** press：捏紧的程度 0..1（按住 Q 时往 1 走）。返回 true ＝ 这一帧捏到了底 */
  update(dt: number, press: number, t: number): boolean;
}

export interface ItemDef {
  id: string;
  name: string;
  /** 日记「拾得」页上的说明 */
  desc: string;
  /** need 必要的（好拿）· collect 收藏品（藏得深、条件难） */
  kind: 'need' | 'collect';
  /** 像素画：得到时的卡片、日记都用它；没写 world() 时也是世界里的纸片（每米 16 像素） */
  icon(): HTMLCanvasElement;
  /** 在世界里、环绕展示时的样子：原点在底面中心。没写就是一张浮着、正面朝人的纸片 */
  world?(): Shown;
  /** nx_get=custom 时：条件满足就得到 */
  check?(ctx: ItemCtx): boolean;
  /** 拿在手里的样子与「捏」的动作（原点在装置的中心） */
  held(): HeldModel;
  /** 捏到底时发生的事（没写就只有模型自己的反应） */
  bloom?(): void;
}

export const ITEMS: ItemDef[] = [compass];

export const itemDef = (id: string) => ITEMS.find((d) => d.id === id);
