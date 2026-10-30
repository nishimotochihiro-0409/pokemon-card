// Cloudflare Worker: public Pokémon deck code -> validated 60-card deck JSON.
// Deploy as a Worker. No GitHub token or other secret is needed.
const OFFICIAL = "https://www.pokemon-card.com";
const ALLOWED_ORIGIN = "https://nishimotochihiro-0409.github.io";
const categories = {deck_pok:"ポケモン",deck_pke:"ポケモン",deck_tech:"その他",deck_gds:"グッズ",deck_tool:"ポケモンのどうぐ",deck_sup:"サポート",deck_sta:"スタジアム",deck_ene:"エネルギー"};
const decode = s => s.replace(/&quot;/g,'"').replace(/&#39;|&#x27;/gi,"'").replace(/&amp;/g,"&").replace(/&lt;/g,"<").replace(/&gt;/g,">");
function attributes(tag) {
  const a = {};
  for (const m of tag.matchAll(/([\w-]+)\s*=\s*(["'])(.*?)\2/gs)) a[m[1].toLowerCase()] = decode(m[3]);
  return a;
}
function parseDeck(html) {
  const cards=[];
  for (const m of html.matchAll(/<input\b[^>]*>/gi)) {
    const a=attributes(m[0]), field=categories[a.id]?a.id:a.name;
    if (!categories[field]) continue;
    for (const x of (a.value||"").matchAll(/(\d{4,6})_(\d{1,2})_(\d+)/g))
      cards.push({cardId:x[1],count:Number(x[2]),category:categories[field]});
  }
  if (cards.reduce((n,c)=>n+c.count,0)!==60) throw Error("公式デッキから60枚を取得できませんでした");
  return cards;
}
async function getOfficial(path) {
  const res=await fetch(OFFICIAL+path,{headers:{"User-Agent":"Mozilla/5.0 (compatible; DeckTraining/1.0)","Accept":"text/html"},cf:{cacheTtl:86400,cacheEverything:true}});
  if(!res.ok) throw Error("公式サイトへの接続に失敗しました ("+res.status+")");
  return await res.text();
}
async function detail(card) {
  const html=await getOfficial("/card-search/details.php/card/"+card.cardId+"/regu/all");
  const title=decode((html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)||[])[1]||"").split(/[|｜]/)[0].trim();
  const candidates=[];
  for (const m of html.matchAll(/<img\b[^>]*>/gi)) {
    const a=attributes(m[0]),src=a["data-src"]||a.src||"";
    if(src.includes("card_images") || src.includes("/card/") || (title&&a.alt===title)) candidates.push(src);
  }
  const path=candidates.map(x=>{try{return new URL(x,OFFICIAL)}catch{return null}}).find(u=>u&&u.origin===OFFICIAL&&u.pathname.includes("/card_images/")&&/\.(png|jpe?g|webp)$/i.test(u.pathname));
  if(title)card.name=title;
  if(path)card.imageUrl=path.href;
  return card;
}
function response(body,status=200,origin=ALLOWED_ORIGIN) {
  return new Response(JSON.stringify(body),{status,headers:{"Content-Type":"application/json; charset=utf-8","Access-Control-Allow-Origin":origin,"Access-Control-Allow-Methods":"GET, OPTIONS","Access-Control-Allow-Headers":"Content-Type","Cache-Control":status===200?"public, max-age=3600":"no-store"}});
}
export default {
  async fetch(request) {
    const url=new URL(request.url);
    if(request.method==="OPTIONS")return new Response(null,{status:204,headers:{"Access-Control-Allow-Origin":ALLOWED_ORIGIN,"Access-Control-Allow-Methods":"GET, OPTIONS","Access-Control-Allow-Headers":"Content-Type"}});
    if(request.method!=="GET"||url.pathname!=="/deck")return response({error:"Not found"},404);
    const code=url.searchParams.get("code")||"";
    if(!/^[A-Za-z0-9-]{10,60}$/.test(code))return response({error:"デッキコードの形式を確認してください"},400);
    try {
      const html=await getOfficial("/deck/confirm.html/deckID/"+encodeURIComponent(code)+"/");
      const cards=parseDeck(html);
      // Limit simultaneous requests to avoid overloading the official site.
      for(let i=0;i<cards.length;i+=4)await Promise.all(cards.slice(i,i+4).map(async c=>{try{await detail(c)}catch(e){console.log("Card",c.cardId,String(e))}}));
      const images=cards.filter(c=>c.imageUrl).length;
      if(images!==cards.length)throw Error("カード画像の取得が完了しませんでした ("+images+"/"+cards.length+"種類)");
      return response({deckCode:code,total:60,cards,source:OFFICIAL+"/deck/confirm.html/deckID/"+code+"/",updatedAt:new Date().toISOString()});
    }catch(e){console.log("Import error",String(e));return response({error:String(e.message||e)},502)}
  }
};
