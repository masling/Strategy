import test from 'node:test';
import assert from 'node:assert/strict';
import { volumeAverages } from '../src/chart.mjs';

test('computes VMA5 and VMA20 from the full source series', () => {
  const rows = Array.from({ length: 22 }, (_, index) => ({ close: 10 + index, volume: (index + 1) * 100 }));
  const averages = volumeAverages(rows);
  assert.equal(averages[3][5], null);
  assert.equal(averages[4][5], 300);
  assert.equal(averages[19][20], 1050);
  assert.equal(averages[21][5], 2000);
  assert.equal(averages[21][20], 1250);
});

test('treats absent volume as zero without producing NaN', () => {
  const averages = volumeAverages([{ close: 1 }, { close: 2 }, { close: 3 }, { close: 4 }, { close: 5 }]);
  assert.equal(averages[4][5], 0);
});
