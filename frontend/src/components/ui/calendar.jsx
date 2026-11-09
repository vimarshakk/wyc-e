import React from "react"; export const Calendar=({value,onChange})=><input type="date" value={value||""} onChange={e=>onChange?.(e.target.value)}/>;
