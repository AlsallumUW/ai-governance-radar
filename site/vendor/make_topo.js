const fs=require('fs'),ts=require('topojson-server'),tc=require('topojson-client'),tsim=require('topojson-simplify');
const G=JSON.parse(fs.readFileSync(process.argv[2]));
G.features.forEach(f=>{f.id=f.id||f.properties.iso_a3;f.properties={}});
let topo=ts.topology({countries:G},1e5);
topo=tsim.presimplify(topo); topo=tsim.simplify(topo,tsim.quantile(topo,0.35));
const land=JSON.parse(fs.readFileSync('node_modules/world-atlas/land-50m.json'));
topo.objects.countries.geometries.forEach(g=>{g.id=g.id});
const out={countries:topo,land:land};
fs.writeFileSync(process.argv[3],JSON.stringify(out));
console.log('countries arcs',topo.arcs.length,'bytes',JSON.stringify(topo).length,'land bytes',JSON.stringify(land).length);
// Low-detail copy for the moving globe (world.topo.lo.json next to the output): simplify arcs, never rings, so shared
// borders stay watertight. Targets: about 15,000 country points and 6,000 land points. scripts/make_topo_lo.py does the
// same in Python from world.topo.json when Node is not available.
const points=t=>t.arcs.reduce((n,a)=>n+a.length,0);
function lo(t,target){const p=tsim.presimplify(JSON.parse(JSON.stringify(t)));let q=0.5,lo=0,hi=1,r=p;
  for(let i=0;i<20;i++){r=tsim.simplify(JSON.parse(JSON.stringify(p)),tsim.quantile(p,q));const n=points(r);if(n>target)lo=q;else hi=q;q=(lo+hi)/2}
  return r}
const loOut={countries:lo(topo,15000),land:lo(land,6000)};
fs.writeFileSync(process.argv[3].replace(/\.json$/,'.lo.json'),JSON.stringify(loOut));
console.log('low-detail points: countries',points(loOut.countries),'land',points(loOut.land));
