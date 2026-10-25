// Agent 4: Debt Sustainability
// France versus euro area ESI, both rebased to 100 at the beginning of the rolling five-year window.
window.debtSustainabilityRebase = function(points) { if (!points || !points.length || !Number.isFinite(points[0][1]) || points[0][1] === 0) return []; const base=points[0][1]; return points.map(([date,value])=>[date,100*value/base]); };
