// Supabase DB 직접 조회 테스트 스크립트
const supabaseUrl = "https://abfjmqnurtjfbflquqsp.supabase.co/rest/v1/";
const supabaseKey = "YOUR_SUPABASE_KEY_HERE";

async function run() {
  try {
    console.log("1. [850_dashboard_site_config] 조회 시도...");
    let res = await fetch(`${supabaseUrl}850_dashboard_site_config?select=*`, {
      headers: {
        'apikey': supabaseKey,
        'Authorization': `Bearer ${supabaseKey}`
      }
    });
    console.log("상태코드:", res.status);
    let data = await res.json();
    console.log("결과 개수:", data.length);
    if (data && data.length > 0) {
      console.log("첫번째 레코드:", JSON.stringify(data[0], null, 2));
    }

    console.log("\n2. [Samyang_Incheon] 데이터 조회 시도...");
    let res2 = await fetch(`${supabaseUrl}Samyang_Incheon?select=*&limit=5`, {
      headers: {
        'apikey': supabaseKey,
        'Authorization': `Bearer ${supabaseKey}`
      }
    });
    console.log("상태코드:", res2.status);
    let data2 = await res2.json();
    console.log("결과 개수:", data2.length);
    if (data2 && data2.length > 0) {
      console.log("데이터 샘플:", JSON.stringify(data2, null, 2));
    } else {
      console.log("조회된 데이터가 없습니다. (빈 배열)");
    }
  } catch (err) {
    console.error("에러 발생:", err);
  }
}

run();
