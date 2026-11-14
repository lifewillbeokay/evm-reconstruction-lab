import {getBook} from '../../../lib/rpc';
export const dynamic='force-dynamic';
export async function GET(request:Request){
  try{return Response.json(await getBook(new URL(request.url).searchParams),{headers:{'Cache-Control':'no-store'}});}
  catch(e){return Response.json({error:(e as Error).message||'The Base RPC is unavailable. Try refreshing.'},{status:e instanceof RangeError?400:503,headers:{'Cache-Control':'no-store'}});}
}
