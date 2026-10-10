/* 现实的字：连着真实站点的名字（晶体、罗盘地图上的站点）。和纸签相对——
   纸签是梦里的东西：像素、不透明的纸、剪出来的缺口、一圈墨线、压一格影子、系着线晃、一翻出来；
   现实的字是光里的东西：全分辨率、没有底、四角一副发丝细的取景角、一圈光晕，不翻，是「对上焦」——
   远时散、虚、取景角张开，走近时字距收拢、变清楚、取景角合上来。
   排法：上一行等宽小字的域名，下一行衬线的站名；拉丁字与汉字分开排（各自的字体、字距），交界处空一点。 */

const LATIN = /[A-Za-z0-9][A-Za-z0-9.'’\-]*/g;

/** 站名按文字拆成段：拉丁一段、汉字一段、间隔号单独一段（两边留白） */
function runs(title: string, parent: HTMLElement) {
  parent.textContent = '';
  let last = 0;
  const push = (s: string, cls: string) => {
    if (!s.trim()) return;
    const span = document.createElement('span');
    span.className = cls;
    span.textContent = s.trim();
    parent.appendChild(span);
  };
  const han = (s: string) => {
    for (const part of s.split(/([·・|/])/)) push(part, /^[·・|/]$/.test(part) ? 'sep' : 'han');
  };
  for (const m of title.matchAll(LATIN)) {
    han(title.slice(last, m.index));
    // 全大写的拉丁字（GITHUB）字距放宽一些
    push(m[0], m[0].length > 1 && m[0] === m[0].toUpperCase() && /[A-Z]/.test(m[0]) ? 'lat caps' : 'lat');
    last = m.index! + m[0].length;
  }
  han(title.slice(last));
}

function hostOf(url: string) {
  try {
    const u = new URL(url, location.href);
    return (u.host + u.pathname).replace(/\/$/, '');
  } catch {
    return '';
  }
}

/** 一枚现实的名字。挂在一个已有的元素上（#label、#maplabel），位置仍由调用方摆 */
export class RealName {
  private host: HTMLDivElement;
  private name: HTMLDivElement;
  private key = '';

  constructor(private el: HTMLElement) {
    el.classList.add('real');
    el.textContent = '';
    this.host = document.createElement('div');
    this.host.className = 'host';
    this.name = document.createElement('div');
    this.name.className = 'name';
    el.append(this.host, this.name);
    this.focus(0);
  }

  set(title: string, url = '') {
    const key = `${title}|${url}`;
    if (key === this.key) return;
    this.key = key;
    runs(title, this.name);
    this.host.textContent = url ? hostOf(url) : '';
    this.host.style.display = this.host.textContent ? '' : 'none';
  }

  /** f：对焦的程度（0 散开、虚，1 清楚）；a：在不在（不透明度，默认跟着对焦）。
      两样分开给：走到晶体跟前、四周化白时字是清楚地淡掉，不是又虚回去 */
  focus(f: number, a = f) {
    const k = (v: number) => Math.max(0, Math.min(1, v));
    this.el.style.setProperty('--f', k(f).toFixed(3));
    this.el.style.setProperty('--a', k(a).toFixed(3));
    this.el.style.visibility = k(a) > 0.002 ? '' : 'hidden';
  }
}
