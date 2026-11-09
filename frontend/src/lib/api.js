import axios from "axios";
const client=axios.create({baseURL:process.env.REACT_APP_API_URL||"http://localhost:8000/api/v1"});
client.interceptors.request.use(config=>{const token=localStorage.getItem("wyc_token");if(token)config.headers.Authorization=`Bearer ${token}`;return config;});
export const api={get:async(path,config)=> (await client.get(path,config)).data,post:async(path,body,config)=> (await client.post(path,body,config)).data,upload:async(path,form)=> (await client.post(path,form,{headers:{"Content-Type":"multipart/form-data"}})).data};
