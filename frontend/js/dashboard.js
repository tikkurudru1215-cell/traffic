/* ============================================================
   dashboard.js — Dashboard tab: metric cards + 5 charts
   ============================================================ */

async function initDashboard() {
  try {
    const [eda, metrics] = await Promise.all([
      apiGet("/api/eda"),
      apiGet("/api/metrics"),
    ]);
    renderMetricCards(metrics);
    renderDashCharts(eda, metrics);
  } catch (e) {
    console.error("Dashboard init:", e);
  }
}

/* ── Metric Cards ─────────────────────────────────────────── */
function renderMetricCards(m) {
  const rf = m.rf, lr = m.lr;
  document.getElementById("mc-dataset").innerHTML =
    `<div class="mc-lbl">Dataset Size</div>
     <div class="mc-val" style="color:var(--blu)">105K</div>
     <div class="mc-sub">rows × 26 features</div>
     <div class="mc-tag tag-b">2 years · 6 junctions</div>`;

  document.getElementById("mc-rf").innerHTML =
    `<div class="mc-lbl">RF Accuracy R²</div>
     <div class="mc-val" style="color:var(--grn)">${(rf.r2*100).toFixed(1)}%</div>
     <div class="mc-sub">variance explained</div>
     <div class="mc-tag tag-g">MAE: ${rf.mae} veh/hr</div>`;

  document.getElementById("mc-lr").innerHTML =
    `<div class="mc-lbl">Baseline LR R²</div>
     <div class="mc-val" style="color:var(--ylw)">${(lr.r2*100).toFixed(1)}%</div>
     <div class="mc-sub">linear regression</div>
     <div class="mc-tag tag-y">MAE: ${lr.mae} veh/hr</div>`;

  const imp = m.improvement || (lr.mae / rf.mae).toFixed(1);
  document.getElementById("mc-imp").innerHTML =
    `<div class="mc-lbl">Improvement</div>
     <div class="mc-val" style="color:var(--red)">${imp}×</div>
     <div class="mc-sub">RF over LR</div>
     <div class="mc-tag tag-g">RMSE: ${rf.rmse} vs ${lr.rmse}</div>`;
}

/* ── Charts ───────────────────────────────────────────────── */
function renderDashCharts(eda, metrics) {
  const HOURS  = Array.from({length:24}, (_,i) => i+":00");
  const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const DAYS   = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];

  // 1) Hourly — weekday vs weekend
  new Chart(document.getElementById("c-hourly"), {
    type: "bar",
    data: {
      labels: HOURS,
      datasets: [
        { label:"Weekday", data: eda.hourly_weekday,
          backgroundColor:"#4d9fff55", borderColor:"#4d9fff", borderWidth:1 },
        { label:"Weekend", data: eda.hourly_weekend,
          backgroundColor:"#9b6dff55", borderColor:"#9b6dff", borderWidth:1 },
      ],
    },
    options: chartDefaults({
      plugins: { legend:{ display:true, labels:{color:"#8a93aa", font:{size:10}, boxWidth:10} } },
      scales: {
        x:{ ticks:{ color:"#50596e", font:{size:9}, maxRotation:0 }, grid:{color:"#1d2535"} },
        y:{ ticks:{ color:"#50596e", font:{size:10} }, grid:{color:"#1d2535"} },
      },
    }),
  });

  // 2) Junction comparison
  const jNames = Object.values(eda.junction_names);
  const jVols  = Object.keys(eda.junction_avg).map(k => eda.junction_avg[k]);
  const jColors = ["#4d9fff","#10d97e","#f5a623","#9b6dff","#ff4d4d","#06b6d4"];
  new Chart(document.getElementById("c-junc"), {
    type:"bar",
    data:{
      labels: jNames,
      datasets:[{ data:jVols, backgroundColor:jColors, borderRadius:5, borderWidth:0 }],
    },
    options: chartDefaults({ indexAxis:"y" }),
  });

  // 3) Weather impact
  const wKeys = Object.keys(eda.weather_avg);
  const wVals = wKeys.map(k => eda.weather_avg[k]);
  const wCols = {Clear:"#10d97e",Clouds:"#8a93aa",Haze:"#f5a623",Drizzle:"#4d9fff",
                  Rain:"#3b82f6",Fog:"#50596e",Thunderstorm:"#ff4d4d"};
  new Chart(document.getElementById("c-weather"), {
    type:"bar",
    data:{
      labels: wKeys,
      datasets:[{
        data: wVals,
        backgroundColor: wKeys.map(k => wCols[k]||"#4d9fff"),
        borderRadius:4, borderWidth:0,
      }],
    },
    options: chartDefaults({
      scales:{
        x:{ticks:{color:"#50596e",font:{size:9}},grid:{color:"#1d2535"}},
        y:{ticks:{color:"#50596e",font:{size:10}},grid:{color:"#1d2535"}},
      },
    }),
  });

  // 4) Monthly trend
  new Chart(document.getElementById("c-monthly"), {
    type:"line",
    data:{
      labels: MONTHS,
      datasets:[{
        data: eda.monthly,
        borderColor:"#4d9fff", fill:true, backgroundColor:"#4d9fff18",
        tension:.4, pointRadius:3, pointBackgroundColor:"#4d9fff",
      }],
    },
    options: chartDefaults(),
  });

  // 5) Distribution
  new Chart(document.getElementById("c-dist"), {
    type:"bar",
    data:{
      labels: eda.dist_labels,
      datasets:[{
        data: eda.dist_counts,
        backgroundColor:"#4d9fff55", borderColor:"#4d9fff",
        borderWidth:1, borderRadius:4,
      }],
    },
    options: chartDefaults({
      scales:{
        x:{ticks:{color:"#50596e",font:{size:9},maxRotation:30},grid:{color:"#1d2535"}},
        y:{ticks:{color:"#50596e",font:{size:10}},grid:{color:"#1d2535"}},
      },
    }),
  });
}
