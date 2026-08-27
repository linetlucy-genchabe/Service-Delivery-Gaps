const pptxgen = require('pptxgenjs');

// Data passed via stdin as JSON
let raw = '';
process.stdin.on('data', d => raw += d);
process.stdin.on('end', () => {
  const { title, rows, week_labels, prev_month_label } = JSON.parse(raw);

  const prs = new pptxgen();
  prs.layout = 'LAYOUT_WIDE'; // 13.3" x 7.5"

  const slide = prs.addSlide();

  // ─── Palette ───────────────────────────────────────────────────────────────
  const NAVY   = '1B3A6B';
  const WHITE  = 'FFFFFF';
  const GREEN  = 'DCFCE7'; const GREEN_TXT  = '166534';
  const YELLOW = 'FEF9C3'; const YELLOW_TXT = '854D0E';
  const RED    = 'FEE2E2'; const RED_TXT    = '991B1B';
  const GREY   = 'F8FAFC'; const GREY_TXT   = '94A3B8';
  const GREY_H = 'EEF2F8';  // indicator column bg
  const GREY_T = 'F1F5F9';  // target column bg
  const PCT_GREEN  = 'BBF7D0'; const PCT_GREEN_TXT  = '14532D';
  const PCT_YELLOW = 'FEF08A'; const PCT_YELLOW_TXT = '713F12';
  const PCT_RED    = 'FECACA'; const PCT_RED_TXT    = '7F1D1D';

  function cellColours(colour) {
    if (colour === 'green')  return { bg: GREEN,  txt: GREEN_TXT };
    if (colour === 'yellow') return { bg: YELLOW, txt: YELLOW_TXT };
    if (colour === 'red')    return { bg: RED,    txt: RED_TXT };
    return { bg: GREY, txt: GREY_TXT };
  }

  function pctColours(colour) {
    if (colour === 'green')  return { bg: PCT_GREEN,  txt: PCT_GREEN_TXT };
    if (colour === 'yellow') return { bg: PCT_YELLOW, txt: PCT_YELLOW_TXT };
    if (colour === 'red')    return { bg: PCT_RED,    txt: PCT_RED_TXT };
    return { bg: GREY, txt: GREY_TXT };
  }

  // ─── Layout ─────────────────────────────────────────────────────────────────
  const MARGIN   = 0.15;
  const W_TOTAL  = 13.3 - MARGIN * 2;
  const H_TOTAL  = 7.5  - MARGIN * 2;

  // Column widths (inches) — indicator + target + prev_month + N weeks + pct
  const N_WEEKS  = week_labels.length;
  const W_IND    = 1.55;
  const W_TGT    = 0.85;
  const W_PCT    = 0.95;
  const W_DATA   = (W_TOTAL - W_IND - W_TGT - W_PCT) / (1 + N_WEEKS); // prev_month + weeks
  const COLS     = [W_IND, W_TGT, W_DATA, ...Array(N_WEEKS).fill(W_DATA), W_PCT];

  // Row heights
  const N_ROWS   = rows.length;
  const H_HEADER = 0.38;
  const H_AVAIL  = H_TOTAL - H_HEADER;
  // Child health row gets 2x height
  const child_idx = rows.findIndex(r => r.key === 'child_health');
  const n_normal  = N_ROWS - (child_idx >= 0 ? 1 : 0);
  const H_NORM    = H_AVAIL / (n_normal + 2); // child = 2x
  const ROW_H     = rows.map(r => r.key === 'child_health' ? H_NORM * 2 : H_NORM);

  // x positions
  let xs = [];
  let cx = MARGIN;
  for (const w of COLS) { xs.push(cx); cx += w; }

  // y positions
  let ys = [MARGIN + H_HEADER];
  for (let i = 0; i < N_ROWS - 1; i++) ys.push(ys[i] + ROW_H[i]);

  const FONT = 'Calibri';
  const FSIZE_H = 8.5;   // header
  const FSIZE_D = 7.5;   // data cells
  const FSIZE_I = 7.5;   // indicator label
  const FSIZE_CHILD = 6.5; // child health mini-lines

  // ─── HEADER ROW ─────────────────────────────────────────────────────────────
  const headers = [title, 'Monthly\nTarget', shorten(prev_month_label),
    ...week_labels.map(shorten), '% of Monthly\nTarget Achieved'];

  headers.forEach((h, ci) => {
    slide.addShape(prs.ShapeType.rect, {
      x: xs[ci], y: MARGIN, w: COLS[ci], h: H_HEADER,
      fill: { color: NAVY }, line: { color: WHITE, width: 1.5 }
    });
    slide.addText(h, {
      x: xs[ci], y: MARGIN, w: COLS[ci], h: H_HEADER,
      fontSize: FSIZE_H, bold: true, color: WHITE, fontFace: FONT,
      align: ci === 0 ? 'left' : 'center', valign: 'middle',
      margin: [0, 3, 0, ci === 0 ? 4 : 3], isTextBox: true,
    });
  });

  // ─── DATA ROWS ──────────────────────────────────────────────────────────────
  rows.forEach((row, ri) => {
    const y = ys[ri];
    const h = ROW_H[ri];
    const isChild = row.key === 'child_health';

    // Indicator label
    slide.addShape(prs.ShapeType.rect, {
      x: xs[0], y, w: COLS[0], h,
      fill: { color: GREY_H }, line: { color: WHITE, width: 1.5 }
    });
    slide.addText(row.label, {
      x: xs[0], y, w: COLS[0], h,
      fontSize: FSIZE_I, bold: true, color: NAVY, fontFace: FONT,
      align: 'left', valign: 'middle', margin: [0, 3, 0, 4],
      wrap: true, isTextBox: true,
    });

    // Target
    slide.addShape(prs.ShapeType.rect, {
      x: xs[1], y, w: COLS[1], h,
      fill: { color: GREY_T }, line: { color: WHITE, width: 1.5 }
    });
    slide.addText(row.target || '', {
      x: xs[1], y, w: COLS[1], h,
      fontSize: FSIZE_D, bold: true, color: '374151', fontFace: FONT,
      align: 'center', valign: 'middle', margin: 0, isTextBox: true,
    });

    // Previous month + weekly data cells
    const all_cells = [row.prev_month, ...row.weeks];
    all_cells.forEach((cell, ci) => {
      const col_i = ci + 2; // offset past indicator + target
      const { bg, txt } = cellColours(cell.colour);

      slide.addShape(prs.ShapeType.rect, {
        x: xs[col_i], y, w: COLS[col_i], h,
        fill: { color: bg }, line: { color: WHITE, width: 1.5 }
      });

      if (isChild && cell.lines && cell.lines.length) {
        // Multi-line child health cell
        const textArr = cell.lines.map((line, li) => ({
          text: line,
          options: {
            fontSize: FSIZE_CHILD, bold: li === 0, color: txt,
            fontFace: FONT, breakLine: li < cell.lines.length - 1,
          }
        }));
        slide.addText(textArr, {
          x: xs[col_i], y: y + 0.04, w: COLS[col_i], h: h - 0.04,
          align: 'left', valign: 'top', margin: [2, 3, 2, 3],
          wrap: true, isTextBox: true,
        });
      } else {
        slide.addText(cell.display || '', {
          x: xs[col_i], y, w: COLS[col_i], h,
          fontSize: FSIZE_D, bold: true, color: txt, fontFace: FONT,
          align: 'center', valign: 'middle', margin: 0,
          wrap: true, isTextBox: true,
        });
      }
    });

    // % Monthly Target Achieved
    const pct_ci = COLS.length - 1;
    const { bg: pbg, txt: ptxt } = pctColours(row.pct_colour);
    slide.addShape(prs.ShapeType.rect, {
      x: xs[pct_ci], y, w: COLS[pct_ci], h,
      fill: { color: pbg }, line: { color: WHITE, width: 1.5 }
    });
    slide.addText(row.pct_target ? row.pct_target + '%' : '', {
      x: xs[pct_ci], y, w: COLS[pct_ci], h,
      fontSize: FSIZE_D, bold: true, color: ptxt, fontFace: FONT,
      align: 'center', valign: 'middle', margin: 0, isTextBox: true,
    });
  });

  prs.writeFile({ fileName: '/tmp/pa_scorecard.pptx' }).then(() => {
    process.stdout.write('OK');
  });
});

function shorten(label) {
  if (!label) return '';
  // "April 2026 – Monthly" → "April"
  // "1 May 2026 – 6 May 2026 (May 2026)" → "May WK1"
  // "15 Jun 2026 – 18 Jun 2026 (June 2026)" → "Jun WK2"
  label = String(label);
  if (label.includes('Monthly')) {
    const m = label.match(/([A-Za-z]+)\s+\d{4}/);
    return m ? m[1] : label;
  }
  const m = label.match(/(\d+)\s+([A-Za-z]+)\s+\d{4}/);
  return m ? m[2].slice(0,3) + ' ' + m[1] : label.slice(0, 12);
}