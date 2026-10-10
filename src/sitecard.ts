/* 窗前的站点卡片：推开窗、凑到窗口往外看时浮出来。
   连着真实的站点，所以和晶体的名字一样不走像素 UI，是全分辨率的平滑字（docs/ui.md「全分辨率的例外」）；
   字体、留白取站点自己的样子（博客：衬线标题、等宽小字、一道细线），字色跟着窗里的天走（WindowSky.tone）。
   浮现而不是弹出：淡入、细线从左往右延展；换一处时往换的方向滑开一点再淡回来。 */
import type { Outlook } from './level';

export class SiteCard {
  private root: HTMLDivElement;
  private keys: HTMLDivElement;
  private kicker: HTMLDivElement;
  private title: HTMLDivElement;
  private desc: HTMLDivElement;
  private idx: HTMLDivElement;
  private switchKeys: HTMLSpanElement;
  shown = false;

  constructor() {
    const div = (cls: string, parent: HTMLElement) => {
      const d = document.createElement('div');
      d.className = cls;
      parent.appendChild(d);
      return d;
    };
    this.root = div('site', document.body);
    this.kicker = div('kicker', this.root);
    this.title = div('title', this.root);
    div('rule', this.root);
    this.desc = div('desc', this.root);
    this.idx = div('idx', this.root);
    this.keys = div('sitekeys', document.body);
    this.keys.innerHTML =
      '<span class="sw"><b>A</b><b>D</b>换一处</span><span><b>E</b>进入</span><span><b>S</b>退回</span>';
    this.switchKeys = this.keys.querySelector('.sw')!;
  }

  private fill(o: Outlook, i: number, n: number) {
    let host = o.url;
    try {
      // 域名带路径（github.com/Traveritas），不带协议和末尾的斜杠
      const u = new URL(o.url, location.href);
      host = (u.host + u.pathname).replace(/\/$/, '') || o.url;
    } catch {
      /* 不是网址就照原样写 */
    }
    // 卡片的字体随站点走：按窗里的天（主题名）挑一套样子，见 index.html 的 .site[data-sky=…]
    this.root.dataset.sky = o.sky.split(':')[0];
    this.kicker.textContent = host;
    this.title.textContent = o.title;
    this.desc.textContent = o.desc;
    this.idx.textContent = n > 1 ? `${i + 1} / ${n}` : '';
    this.switchKeys.style.display = n > 1 ? '' : 'none';
  }

  show(o: Outlook, i: number, n: number) {
    this.fill(o, i, n);
    this.shown = true;
    this.root.classList.remove('away-l', 'away-r');
    this.root.classList.add('on');
    this.keys.classList.add('on');
  }

  hide() {
    this.shown = false;
    this.root.classList.remove('on');
    this.keys.classList.remove('on');
  }

  /** 换一处：先往 dir 那边滑开、淡掉（swapOut），换好以后 swapIn 从另一边回来 */
  swapOut(dir: number) {
    this.root.classList.add(dir > 0 ? 'away-l' : 'away-r');
    this.root.classList.remove('on');
  }

  swapIn(o: Outlook, i: number, n: number) {
    this.fill(o, i, n);
    this.root.classList.remove('away-l', 'away-r');
    this.root.classList.add('on');
  }

  /** 字色：窗里的天亮时用深墨，暗时用浅墨；光晕取天的底色，压在流动的线上也读得清 */
  tone(t: { bg: string; ink: string; dark: boolean }) {
    for (const el of [this.root, this.keys]) {
      el.style.setProperty('--ink', t.ink);
      el.style.setProperty('--bg', t.bg);
    }
  }
}
