// Physical curb parking areas are displayed separately from placement eligibility.
export function parkingPositions(map){return [...(map.parking_spaces||[]),...(map.parking_excluded||[])]}
export function parkingStyle(bay,occupied=false,light=false){
 if(occupied)return {key:'occupied',label:'Occupied',color:light?'#606b75':'#8f9da7',fill:'#7b899499'};
 return {key:'available',label:'Open',color:light?'#7850b1':'#b79bff',fill:light?'#7751c570':'#b79bff70'};
}
export function parkingExplanation(bay){return 'Open when unoccupied. Vehicle fit and a clear physical maneuver are checked when assigning a destination.'}

export function parkingOccupancy(state={}){const occupied={...(state.occupied||{})};for(const [bay,id] of Object.entries(state.reserved||{}))if(!occupied[bay])occupied[bay]={kind:'actor',id,approaching:true};return occupied}
