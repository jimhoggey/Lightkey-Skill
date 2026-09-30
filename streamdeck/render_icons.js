// Renders Stream Deck key icons (144 x 144 PNG) and preview sheets with AppKit, through JXA,
// so nothing needs installing on a Mac. Driven by the JSON spec streamdeck/profile.py writes.
//
// Usage: osascript -l JavaScript render_icons.js <spec.json>
//
// Off state: dark key, coloured ring, white text, a strip of the cue's colours along the bottom.
// On state:  the cue's colours as a gradient fill, an inner ring and a LIVE pill, so a lit key reads
//            as lit even when the colour is pale.
ObjC.import('AppKit');

const S = 144;
const BG = '#0D0D0F';

function readJSON(p) {
  return JSON.parse(ObjC.unwrap($.NSString.stringWithContentsOfFileEncodingError(p, $.NSUTF8StringEncoding, null)));
}
function rgb(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(v => v / 255); }
function col(h, a) { const c = rgb(h); return $.NSColor.colorWithDeviceRedGreenBlueAlpha(c[0], c[1], c[2], a === undefined ? 1 : a); }
function bitmap(w, h) {
  return $.NSBitmapImageRep.alloc.initWithBitmapDataPlanesPixelsWidePixelsHighBitsPerSampleSamplesPerPixelHasAlphaIsPlanarColorSpaceNameBytesPerRowBitsPerPixel(
    null, w, h, 8, 4, true, false, $.NSDeviceRGBColorSpace, 0, 0);
}
function begin(r) {
  $.NSGraphicsContext.saveGraphicsState;
  $.NSGraphicsContext.setCurrentContext($.NSGraphicsContext.graphicsContextWithBitmapImageRep(r));
}
function finish(r, file) {
  $.NSGraphicsContext.restoreGraphicsState;
  r.representationUsingTypeProperties($.NSBitmapImageFileTypePNG, $({})).writeToFileAtomically(file, true);
}
function rect(x, yTop, w, h, H) { return $.NSMakeRect(x, H - yTop - h, w, h); }   // top-down helper
function fill(h, r) { col(h).setFill; $.NSRectFill(r); }
function gradient(colors, r, angle) {
  if (colors.length === 1) { fill(colors[0], r); return; }
  $.NSGradient.alloc.initWithColors($(colors.map(c => col(c)))).drawInRectAngle(r, angle);
}
function font(size, weight) { return $.NSFont.systemFontOfSizeWeight(size, weight); }
function attrs(f, h, kern, alpha) {
  const d = $.NSMutableDictionary.alloc.init;
  d.setObjectForKey(f, $.NSFontAttributeName);
  d.setObjectForKey(col(h, alpha), $.NSForegroundColorAttributeName);
  if (kern) d.setObjectForKey($.NSNumber.numberWithDouble(kern), $.NSKernAttributeName);
  return d;
}
function ns(t) { return $.NSString.alloc.initWithUTF8String(t); }
function width(t, a) { return ns(t).sizeWithAttributes(a).width; }
// Draw one line centred on cx with its baseline at yBase (top-down).
function line(t, f, a, cx, yBase, H) {
  ns(t).drawAtPointWithAttributes($.NSMakePoint(cx - width(t, a) / 2, H - yBase + f.descender), a);
}
// Largest heavy font (<= start) at which every line fits maxW and the cap-height stack fits maxH.
function fit(lines, maxW, maxH, start, minSize, ink) {
  for (let size = start; size >= minSize; size -= 1) {
    const f = font(size, $.NSFontWeightHeavy), a = attrs(f, ink, 0);
    const cap = f.capHeight, gap = cap * 0.46;
    const h = lines.length * cap + (lines.length - 1) * gap;
    if (Math.max.apply(null, lines.map(l => width(l, a))) <= maxW && h <= maxH) return { f: f, a: a, cap: cap, gap: gap, h: h };
  }
  const f = font(minSize, $.NSFontWeightHeavy), a = attrs(f, ink, 0);
  return { f: f, a: a, cap: f.capHeight, gap: f.capHeight * 0.46, h: lines.length * f.capHeight * 1.46 };
}
function stack(lines, top, bottom, maxW, start, ink, H) {
  const t = fit(lines, maxW, bottom - top, start, 14, ink);
  let y = (top + bottom) / 2 - t.h / 2 + t.cap;
  lines.forEach(l => { line(l, t.f, t.a, S / 2, y, H); y += t.cap + t.gap; });
}
function label(text, yBase, maxW, ink, alpha) {
  for (let size = 19; size >= 10; size -= 1) {
    const f = font(size, $.NSFontWeightHeavy), a = attrs(f, ink, 1.2, alpha);
    if (width(text, a) <= maxW || size === 10) { line(text, f, a, S / 2, yBase, S); return; }
  }
}

function drawKey(k) {
  const r = bitmap(S, S); begin(r);
  const full = $.NSMakeRect(0, 0, S, S);
  if (k.state === 'on') {
    gradient(k.colors, full, 315);
    const ring = $.NSBezierPath.bezierPathWithRoundedRectXRadiusYRadius($.NSMakeRect(5, 5, S - 10, S - 10), 17, 17);
    ring.setLineWidth(6); col(k.ink, 0.9).setStroke; ring.stroke;
    label(k.category, 30, S - 30, k.ink, 0.85);
    stack(k.lines, 40, 104, S - 24, 50, k.ink, S);
    const pw = 58, ph = 22, px = (S - pw) / 2, py = 112;
    const pill = $.NSBezierPath.bezierPathWithRoundedRectXRadiusYRadius(rect(px, py, pw, ph, S), 11, 11);
    col(k.ink).setFill; pill.fill;
    const pf = font(14, $.NSFontWeightHeavy), pa = attrs(pf, k.pillInk, 1.5);
    line('LIVE', pf, pa, S / 2, py + ph / 2 + pf.capHeight / 2, S);
  } else {
    fill(BG, full);
    const ring = $.NSBezierPath.bezierPathWithRoundedRectXRadiusYRadius($.NSMakeRect(5, 5, S - 10, S - 10), 17, 17);
    ring.setLineWidth(5); col(k.accent).setStroke; ring.stroke;
    label(k.category, 30, S - 30, k.accent, 1);
    stack(k.lines, 40, 108, S - 24, 50, "#FFFFFF", S);
    const strip = rect(22, 116, S - 44, 10, S);
    $.NSGraphicsContext.saveGraphicsState;
    $.NSBezierPath.bezierPathWithRoundedRectXRadiusYRadius(strip, 5, 5).addClip;
    gradient(k.colors, strip, 0);
    $.NSGraphicsContext.restoreGraphicsState;
  }
  finish(r, k.file);
}

function drawLabel(k) {
  const r = bitmap(S, S); begin(r);
  fill('#000000', $.NSMakeRect(0, 0, S, S));
  label(k.sub, 30, S - 20, '#8E8E93', 1);
  stack(k.lines, 42, 122, S - 24, 34, '#FFFFFF', S);
  finish(r, k.file);
}

function drawSheet(sh) {
  const c = sh.cell, g = sh.gap, pad = 28, th = 34;
  const gc = sh.gridCols || 5, gr = sh.gridRows || 3;
  const bw = gc * c + (gc - 1) * g, bh = gr * c + (gr - 1) * g;
  const cols = sh.columns, rows = Math.ceil(sh.blocks.length / cols);
  const W = pad + cols * (bw + pad), H = 64 + rows * (th + bh + pad);
  const r = bitmap(W, H); begin(r);
  fill('#1C1C1E', $.NSMakeRect(0, 0, W, H));
  const tf = font(26, $.NSFontWeightHeavy), ta = attrs(tf, '#FFFFFF', 0);
  ns(sh.title).drawAtPointWithAttributes($.NSMakePoint(pad, H - 44 + tf.descender), ta);
  sh.blocks.forEach((b, i) => {
    const bx = pad + (i % cols) * (bw + pad), by = 64 + Math.floor(i / cols) * (th + bh + pad);
    const bf = font(17, $.NSFontWeightBold), ba = attrs(bf, '#D1D1D6', 0);
    ns(b.title).drawAtPointWithAttributes($.NSMakePoint(bx, H - by - 22 + bf.descender), ba);
    b.cells.forEach((row, ry) => row.forEach((cell, cx) => {
      const kr = rect(bx + cx * (c + g), by + th + ry * (c + g), c, c, H);
      $.NSGraphicsContext.saveGraphicsState;
      $.NSBezierPath.bezierPathWithRoundedRectXRadiusYRadius(kr, 12, 12).addClip;
      fill('#000000', kr);
      if (cell === 'NEXT' || cell === 'PREV') {
        const nf = font(13, $.NSFontWeightBold), na = attrs(nf, '#8E8E93', 0);
        const t = cell === 'NEXT' ? 'NEXT ▶' : '◀ PREV';
        ns(t).drawAtPointWithAttributes($.NSMakePoint(kr.origin.x + (c - width(t, na)) / 2, kr.origin.y + c / 2 - 6), na);
      } else if (cell) {
        $.NSImage.alloc.initWithContentsOfFile(cell).drawInRectFromRectOperationFraction(kr, $.NSMakeRect(0, 0, 0, 0), 2, 1.0);
      }
      $.NSGraphicsContext.restoreGraphicsState;
    }));
  });
  finish(r, sh.file);
}

function run(argv) {
  const spec = readJSON(argv[0]);
  spec.icons.forEach(k => (k.kind === 'label' ? drawLabel : drawKey)(k));
  (spec.sheets || []).forEach(drawSheet);
  return `rendered ${spec.icons.length} icons, ${(spec.sheets || []).length} sheets`;
}
