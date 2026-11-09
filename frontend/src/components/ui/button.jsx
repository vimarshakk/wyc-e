import React from "react";
export const Button=React.forwardRef(({className="",variant="default",...props},ref)=><button ref={ref} className={`button ${variant==="primary"?"primary":""} ${className}`} {...props}/>); Button.displayName="Button";
