/* 中英两套字。界面上的字都从这里取：t('键') 取一句，带参数的写成函数。
   场景里写死的字（Blender 的 nx_title、nx_pose_title）按中文原文查 SCENE 表，tr(原文) 换成当前语言；查不到照原样。
   连着真实站点的名字（晶体、窗外的站点卡片的站名）不翻：清晰的东西就是真实的东西。
   语言存在 nexus:settings 的 lang 里；没存过就看浏览器的语言。调试信息不翻。 */

export type Lang = 'zh' | 'en';
/** 一句两种写法（物品、世界名这类跟着各自模块走的字用它） */
export type L = Record<Lang, string>;

const SETTINGS_KEY = 'nexus:settings';

function initial(): Lang {
  try {
    const s = JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? '{}');
    if (s.lang === 'zh' || s.lang === 'en') return s.lang;
  } catch {
    /* 看浏览器 */
  }
  return /^zh\b/i.test(navigator.language ?? '') ? 'zh' : 'en';
}

export let lang: Lang = initial();
export const setLang = (l: Lang) => (lang = l);
export const l = (s: L) => s[lang];

const STR = {
  // 开场
  clickToWake: { zh: '点击醒来', en: 'click to wake' },
  // 日记：索引贴
  tabRecord: { zh: '记录', en: 'Log' },
  tabItems: { zh: '拾得', en: 'Found' },
  tabSettings: { zh: '设置', en: 'Settings' },
  // 日记：记录
  now: { zh: '此刻在', en: 'Now in' },
  awakeNow: { zh: '此刻 · 醒着', en: 'Now · awake' },
  visited: { zh: '去过', en: 'Places' },
  paths: { zh: '走过的路', en: 'Paths' },
  sites: { zh: '站点', en: 'Sites' },
  found: { zh: '拾得', en: 'Found' },
  wake: { zh: '醒来', en: 'Wake up' },
  visitedList: { zh: '去过的地方', en: 'Places been' },
  close: { zh: 'Tab 合上', en: 'Tab to close' },
  // 日记：拾得
  none: { zh: '（还没有）', en: '(nothing yet)' },
  inHand: { zh: '手里', en: 'held' },
  foundHere: { zh: '捡到的东西会记在这里', en: 'What you pick up goes here' },
  clickToHold: { zh: '点名字拿起', en: 'Click to hold' },
  clickToStow: { zh: '点名字收起', en: 'Click to stow' },
  // 日记：设置
  settings: { zh: '设置', en: 'Settings' },
  sens: { zh: '视角灵敏度', en: 'Look speed' },
  res: { zh: '画面', en: 'Picture' },
  language: { zh: '语言', en: 'Language' },
  hud: { zh: '调试信息', en: 'Debug info' },
  on: { zh: '开', en: 'on' },
  off: { zh: '关', en: 'off' },
  resAuto: { zh: '自动', en: 'Auto' },
  resFull: { zh: '精细', en: 'Fine' },
  resHalf: { zh: '流畅', en: 'Smooth' },
  resQuarter: { zh: '极速', en: 'Fast' },
  resEighth: { zh: '马赛克', en: 'Mosaic' },
  resSixteenth: { zh: '印象派', en: 'Monet' },
  // 日记：操作
  controls: { zh: '操作', en: 'Controls' },
  kWalk: { zh: '行走', en: 'Walk' },
  kJump: { zh: '跳', en: 'Jump' },
  kHurry: { zh: '快走', en: 'Hurry' },
  kUse: { zh: '互动', en: 'Use' },
  kDiary: { zh: '日记', en: 'Diary' },
  kSqueeze: { zh: '捏住手里的', en: 'Squeeze' },
  kCarried: { zh: '看看身上的', en: 'Look over' },
  kFree: { zh: '放开鼠标', en: 'Free mouse' },
  // 物品
  pickUp: { zh: '拾起', en: 'Pick up' },
  got: { zh: '得到了', en: 'Got' },
  releaseToHold: { zh: '松开 F 拿起', en: 'Let go of F to hold' },
  carryingNothing: { zh: '身上还没有东西', en: 'Not carrying anything' },
  awakeNothing: { zh: '醒着，什么也没带出来', en: 'Awake. Nothing came with you' },
  // 罗盘的地图
  site: { zh: '站点', en: 'Site' },
  here: { zh: '此刻', en: 'Now' },
  // 窗前的站点卡片
  switchPlace: { zh: '换一处', en: 'Other' },
  enter: { zh: '进入', en: 'Enter' },
  back: { zh: '退回', en: 'Back' },
} satisfies Record<string, L>;

export type Key = keyof typeof STR;
export const t = (k: Key) => STR[k][lang];

/** 带数的几句 */
export const night = (n: number) => (lang === 'zh' ? `第 ${n} 夜` : `Night ${n}`);
export const andMore = (n: number) => (lang === 'zh' ? `……还有 ${n} 处` : `…and ${n} more`);
export const gotOn = (n: number, where: string) => (lang === 'zh' ? `第 ${n} 夜 · 在${where}` : `Night ${n} · ${where}`);

/** 场景里写死的字：中文原文 → 英文 */
const SCENE: Record<string, string> = {
  一杯水: 'A glass of water',
  翻开: 'Open',
  凑近: 'Lean in',
  睡: 'Sleep',
  开灯: 'Lights on',
  关灯: 'Lights off',
  开门: 'Open',
  关门: 'Close',
  推开窗: 'Open',
  关上窗: 'Close',
  打开柜门: 'Open',
  关上柜门: 'Close',
  杯里: 'Into the cup',
  螺旋梯顶: 'Top of the spiral',
  测试出口: 'Test exit',
  下沉: 'Descent',
  花房: 'Glasshouse',
  云阶: 'Cloud steps',
  回廊: 'Cloister',
  无墙之屋: 'Wallless room',
  浅滩: 'Shoal',
};

export const tr = (s: string) => (lang === 'zh' ? s : (SCENE[s] ?? s));
