export function pearson(xs: number[], ys: number[]) {
  const n = xs.length;
  if (n < 3) return { r: null as number | null, n };
  const mx = xs.reduce((a, b) => a + b, 0) / n;
  const my = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0;
  let dx = 0;
  let dy = 0;
  for (let i = 0; i < n; i++) {
    const x = xs[i] - mx;
    const y = ys[i] - my;
    num += x * y;
    dx += x * x;
    dy += y * y;
  }
  if (!dx || !dy) return { r: null, n };
  return { r: num / Math.sqrt(dx * dy), n };
}
