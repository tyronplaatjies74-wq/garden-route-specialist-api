import { NextRequest, NextResponse } from 'next/server';
const VERIFY_TOKEN = "garden_route_123";
export async function GET(req: NextRequest) {
  const p = req.nextUrl.searchParams;
  if (p.get("hub.mode")==="subscribe" && p.get("hub.verify_token")===VERIFY_TOKEN) {
    return new NextResponse(p.get("hub.challenge"), {status:200});
  }
  return new NextResponse("Forbidden", {status:403});
}
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const msg = body.entry?.[0]?.changes?.[0]?.value?.messages?.[0];
    if (!msg?.from || !msg?.text?.body) return NextResponse.json({status:"ok"});
    const text = msg.text.body;
    const reply = `Garden Route Specialist: Got "${text}"! I can help with routes, stays in Knysna/Plett/George, and local guides. What do you need?`;
    await fetch(`https://graph.facebook.com/v18.0/${process.env.WHATSAPP_PHONE_ID}/messages`,{
      method:"POST",
      headers:{"Authorization":`Bearer ${process.env.WHATSAPP_TOKEN}`,"Content-Type":"application/json"},
      body:JSON.stringify({messaging_product:"whatsapp",to:msg.from,text:{body:reply}})
    });
    return NextResponse.json({status:"sent"});
  } catch(e) { return NextResponse.json({error:"fail"}, {status:500}); }
}