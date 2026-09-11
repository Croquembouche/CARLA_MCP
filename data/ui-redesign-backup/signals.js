export const signalColors={Red:'#e75359',Yellow:'#f1bd3d',Green:'#27c787',Off:'#7d8d97',Unknown:'#8794b8'};
export const isSignal=a=>a.type.startsWith('traffic.traffic_light');
export const signalPoint=a=>a.heads?.[0]||a.pose;
export function drawSignal(g,a,x,y,selected=false,light=false,label=true){
 g.save();g.translate(x,y);g.fillStyle=light?'#f7fafc':'#10202c';g.strokeStyle=selected?'#42d9ae':light?'#56717e':'#9eb4c1';g.lineWidth=selected?2.5:1;
 g.beginPath();g.roundRect(-6,-15,12,30,3);g.fill();g.stroke();
 for(const [i,s] of ['Red','Yellow','Green'].entries()){g.fillStyle=a.state===s?signalColors[s]:(light?'#aab8c0':'#34454f');g.beginPath();g.arc(0,-9+i*9,3.2,0,Math.PI*2);g.fill()}
 if(label){const text=`${a.id}${a.frozen?' ▣':''}`;g.font='bold 10px system-ui';g.textAlign='left';g.fillStyle=light?'#f7fafc':'#10202c';g.fillRect(9,-7,g.measureText(text).width+5,14);g.fillStyle=light?'#243d4a':'#e6f2f6';g.fillText(text,11,4)}
 if(a.state==='Off'||a.state==='Unknown'){g.fillStyle=light?'#243d4a':'#ffffff';g.font='bold 11px system-ui';g.textAlign='center';g.fillText(a.state==='Off'?'×':'?',0,4)}g.restore();
}
