import {simulate} from '../../../lib/simulation';
export async function POST(request:Request){
  try{
    const text=await request.text();if(text.length>12000)return Response.json({error:'Scenario is too large.'},{status:400});
    const input=JSON.parse(text);if(!input||typeof input!=='object')return Response.json({error:'Invalid scenario.'},{status:400});
    return Response.json(await simulate(input),{headers:{'Cache-Control':'no-store'}});
  }catch(e){return Response.json({error:(e as Error).message},{status:e instanceof RangeError||e instanceof SyntaxError?400:502,headers:{'Cache-Control':'no-store'}});}
}
