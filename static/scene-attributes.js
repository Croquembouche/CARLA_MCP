// World-aligned native materials can leave UV0 undefined. Keep browser UVs finite.
export function repairUV(position,uv){let repaired=0;for(let i=0;i<uv.length;i++)if(!Number.isFinite(uv[i])){uv[i]=position[Math.floor(i/2)*3+(i%2?2:0)];repaired++}return repaired;}
