/**
 * ECharts 数据可视化渲染（单月数据 + 环比）
 * 包含：指标卡、开发投资、销售、待售、开工竣工、到位资金、70城房价、房企排行
 */
(function () {
  var D = window.SALES_DATA || {};
  var periods = D.periods || [];
  var ec = window.echarts;

  /* 注册全局主题：统一字号与颜色，避免逐个配置遗漏 */
  if (ec) {
    ec.registerTheme('rere', {
      textStyle: { fontSize: 15, color: '#1f2a44' },
      title: { textStyle: { fontSize: 16, color: '#0d1729' } },
      legend: { textStyle: { fontSize: 15, color: '#1f2a44' } },
      tooltip: { textStyle: { fontSize: 15 } },
      categoryAxis: {
        axisLabel: { fontSize: 15, color: '#1f2a44' },
        nameTextStyle: { fontSize: 14, color: '#5a6580' }
      },
      valueAxis: {
        axisLabel: { fontSize: 15, color: '#1f2a44' },
        nameTextStyle: { fontSize: 14, color: '#2c3a55' }
      }
    });
  }

  // 统一颜色
  var C = {
    primary: '#1f6feb', primary2: '#4f95ff', accent: '#f59e0b',
    up: '#e5484d', down: '#16a34a', purple: '#7c3aed', teal: '#0ea5e9',
    bar2: '#8ab0ff', bar3: '#cfe0ff'
  };

  function sign(v) { return v == null ? '' : (v >= 0 ? '+' : '') + v; }
  function fmt(n) { return n == null ? '—' : n.toLocaleString('zh-CN'); }

  function momColor(v) {
    if (v == null) return C.primary;
    return v >= 0 ? C.up : C.down;
  }

  function init(id) {
    var dom = document.getElementById(id);
    if (!dom || !ec) return null;
    return ec.init(dom, 'rere');
  }

  /* ===== 指标卡（单月 + 环比）===== */
  function renderMetrics() {
    var box = document.getElementById('metricGrid');
    if (!box) return;

    // 取最新一期（数组最后一项）作为指标卡展示值
    var n = periods.length - 1;
    var lastPeriod = periods[n] || '';
    // 同步标题月份：📌 核心指标概览（2026年{lastPeriod}单月）
    var titleEl = document.getElementById('metricTitle');
    if (titleEl && lastPeriod) {
      titleEl.textContent = '📌 核心指标概览（2026年' + lastPeriod + '单月）';
    }
    function lastOr(arr, fallback) {
      if (!arr || !arr.length) return fallback;
      var v = arr[arr.length - 1];
      return v == null ? fallback : v;
    }

    var inv = D.investment || {};
    var s = D.sales || {};
    var con = D.construction || {};
    var f = D.funding || {};
    var dev = (D.developers || {}).scales || [];
    var scale0 = dev[0] || {};

    var items = [
      { label: '房地产开发投资', value: lastOr(inv.total, 0), unit: '亿元',
        mom: lastOr((inv.mom || {}).total, null), period: lastPeriod + '单月' },
      { label: '新建商品房销售额', value: lastOr(s.amount, 0), unit: '亿元',
        mom: lastOr((s.mom || {}).amount, null), period: lastPeriod + '单月' },
      { label: '商品房销售面积', value: lastOr(s.area, 0), unit: '万㎡',
        mom: lastOr((s.mom || {}).area, null), period: lastPeriod + '单月' },
      { label: '房屋新开工面积', value: lastOr(con.newStart, 0), unit: '万㎡',
        mom: lastOr((con.mom || {}).newStart, null), period: lastPeriod + '单月' },
      { label: '房企到位资金', value: lastOr(f.total, 0), unit: '亿元',
        mom: lastOr((f.mom || {}).total, null), period: lastPeriod + '单月' },
      { label: 'TOP100房企销售额', value: scale0.value || 0, unit: '亿元',
        mom: scale0.mom != null ? scale0.mom : null,
        period: lastPeriod + '单月·' + (scale0.label ? scale0.label.split('(')[0].replace('TOP100','').trim() : '全口径') }
    ];
    box.innerHTML = items.map(function (it) {
      var nullMom = it.mom == null;
      var cls = nullMom ? '' : (it.mom >= 0 ? 'yoy-up' : 'yoy-down');
      var arrow = nullMom ? '·' : (it.mom >= 0 ? '▲' : '▼');
      var momTxt = nullMom ? '—' : (sign(it.mom) + '%');
      return (
        '<div class="metric-card">' +
          '<div class="m-label">' + it.label + '</div>' +
          '<div class="m-value">' + fmt(it.value) + '<span class="m-unit">' + it.unit + '</span></div>' +
          '<div class="m-yoy ' + cls + '">' + arrow + ' 环比 ' + momTxt + '</div>' +
        '</div>'
      );
    }).join('');
  }

  /* ===== 累计指标卡（1-N月累计 + 同比）===== */
  function renderCumMetrics() {
    var box = document.getElementById('cumMetricGrid');
    if (!box) return;
    var cy = D.cumYoy || {};
    var items = cy.items || [];
    var period = cy.period || '';
    // 同步累计模块标题月份
    var titleEl = document.getElementById('cumMetricTitle');
    if (titleEl && period) {
      titleEl.textContent = '📊 累计指标概览（2026年' + period + '）';
    }
    if (!items.length) { box.innerHTML = '<div style="padding:20px;color:#888">暂无累计数据</div>'; return; }

    box.innerHTML = items.map(function (it) {
      var nullYoy = it.yoy == null;
      var cls = nullYoy ? '' : (it.yoy >= 0 ? 'yoy-up' : 'yoy-down');
      var arrow = nullYoy ? '·' : (it.yoy >= 0 ? '▲' : '▼');
      var yoyTxt = nullYoy ? '—' : (sign(it.yoy) + '%');
      return (
        '<div class="metric-card cum-card">' +
          '<div class="m-label">' + it.label + '</div>' +
          '<div class="m-value">' + fmt(it.value) + '<span class="m-unit">' + it.unit + '</span></div>' +
          '<div class="m-yoy ' + cls + '">' + arrow + ' 同比 ' + yoyTxt + '</div>' +
        '</div>'
      );
    }).join('');
  }

  /* ===== 1. 开发投资（单月 + 环比）===== */
  function chartInvestment() {
    var chart = init('chart-investment'); if (!chart) return;
    var inv = D.investment;
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: ['开发投资总额', '住宅投资', '总额环比'], top: 0  },
      grid: { left: 60, right: 60, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: periods },
      yAxis: [
        { type: 'value', name: '亿元', axisLabel: { formatter: '{value}' } },
        { type: 'value', name: '环比%', axisLabel: { formatter: '{value}%' }, splitLine: { show: false } }
      ],
      series: [
        { name: '开发投资总额', type: 'bar', data: inv.total, itemStyle: { color: C.primary }, barWidth: 18 },
        { name: '住宅投资', type: 'bar', data: inv.residential, itemStyle: { color: C.primary2 }, barWidth: 18 },
        {
          name: '总额环比', type: 'line', yAxisIndex: 1, data: inv.mom.total,
          itemStyle: { color: C.accent }, lineStyle: { width: 2.5 },
          label: { show: true, formatter: function (p) { return p.value == null ? '—' : p.value + '%'; }, fontSize: 15 }
        }
      ]
    });
    return chart;
  }

  /* ===== 2. 商品房销售（单月 + 环比）===== */
  function chartSales() {
    var chart = init('chart-sales'); if (!chart) return;
    var s = D.sales;
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: ['销售额(亿元)', '销售面积(万㎡)', '销售额环比'], top: 0  },
      grid: { left: 60, right: 70, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: periods },
      yAxis: [
        { type: 'value', name: '亿元', position: 'left' },
        { type: 'value', name: '万㎡ / %', position: 'right', splitLine: { show: false } }
      ],
      series: [
        { name: '销售额(亿元)', type: 'bar', data: s.amount, itemStyle: { color: C.primary }, barWidth: 22 },
        { name: '销售面积(万㎡)', type: 'line', yAxisIndex: 1, data: s.area, itemStyle: { color: C.teal }, lineStyle: { width: 2.5 }, symbol: 'circle', symbolSize: 8 },
        {
          name: '销售额环比', type: 'line', yAxisIndex: 1, data: s.mom.amount,
          itemStyle: { color: C.accent }, lineStyle: { width: 2, type: 'dashed' },
          label: { show: true, formatter: function (p) { return p.value == null ? '—' : p.value + '%'; }, fontSize: 15 }
        }
      ]
    });
    return chart;
  }

  /* ===== 3. 商品房单月销售面积与环比 ===== */
  function chartSalesMoM() {
    var chart = init('chart-sales-mom'); if (!chart) return;
    var s = D.sales;
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: ['单月销售面积(万㎡)', '环比增速'], top: 0  },
      grid: { left: 60, right: 60, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: periods },
      yAxis: [
        { type: 'value', name: '万㎡' },
        { type: 'value', name: '环比%', axisLabel: { formatter: '{value}%' }, splitLine: { show: false } }
      ],
      series: [
        { name: '单月销售面积(万㎡)', type: 'bar', data: s.area, itemStyle: { color: C.primary2 }, barWidth: 26 },
        {
          name: '环比增速', type: 'line', yAxisIndex: 1, data: s.mom.area,
          itemStyle: { color: C.accent }, lineStyle: { width: 2.5 },
          label: { show: true, formatter: function (p) { return p.value == null ? '—' : p.value + '%'; }, fontSize: 15 },
          connectNulls: true
        }
      ]
    });
    return chart;
  }

  /* ===== 4. 待售面积（期末值 + 环比）===== */
  function chartInventory() {
    var chart = init('chart-inventory'); if (!chart) return;
    var inv = D.inventory;
    chart.setOption({
      tooltip: { trigger: 'axis'  },
      legend: { data: ['待售总面积', '住宅待售面积'], top: 0  },
      grid: { left: 60, right: 30, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: periods },
      yAxis: { type: 'value', name: '万㎡' },
      series: [
        { name: '待售总面积', type: 'line', data: inv.total, itemStyle: { color: C.primary }, lineStyle: { width: 3 }, symbol: 'circle', symbolSize: 8, areaStyle: { opacity: 0.12 } },
        { name: '住宅待售面积', type: 'line', data: inv.residential, itemStyle: { color: C.accent }, lineStyle: { width: 3 }, symbol: 'circle', symbolSize: 8 }
      ]
    });
    return chart;
  }

  /* ===== 5. 新开工/竣工（单月 + 环比）===== */
  function chartConstruction() {
    var chart = init('chart-construction'); if (!chart) return;
    var c = D.construction;
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: ['新开工(万㎡)', '竣工(万㎡)', '新开工环比', '竣工环比'], top: 0  },
      grid: { left: 60, right: 60, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: periods },
      yAxis: [
        { type: 'value', name: '万㎡(单月)' },
        { type: 'value', name: '环比%', axisLabel: { formatter: '{value}%' }, splitLine: { show: false } }
      ],
      series: [
        { name: '新开工(万㎡)', type: 'bar', data: c.newStart, itemStyle: { color: C.primary }, barWidth: 16 },
        { name: '竣工(万㎡)', type: 'bar', data: c.complete, itemStyle: { color: C.teal }, barWidth: 16 },
        { name: '新开工环比', type: 'line', yAxisIndex: 1, data: c.mom.newStart, itemStyle: { color: C.accent }, lineStyle: { width: 2, type: 'dashed' },
          label: { show: true, formatter: function (p) { return p.value == null ? '—' : p.value + '%'; }, fontSize: 15 } },
        { name: '竣工环比', type: 'line', yAxisIndex: 1, data: c.mom.complete, itemStyle: { color: C.purple }, lineStyle: { width: 2, type: 'dashed' },
          label: { show: true, formatter: function (p) { return p.value == null ? '—' : p.value + '%'; }, fontSize: 15 } }
      ]
    });
    return chart;
  }

  /* ===== 6. 到位资金结构（单月 + 环比）===== */
  function chartFunding() {
    var chart = init('chart-funding'); if (!chart) return;
    var f = D.funding;
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: ['国内贷款', '自筹资金', '定金及预收款', '个人按揭贷款', '到位资金总额'], top: 0  },
      grid: { left: 60, right: 60, top: 50, bottom: 30 },
      xAxis: { type: 'category', data: periods },
      yAxis: [
        { type: 'value', name: '亿元(单月)' },
        { type: 'value', name: '总额', splitLine: { show: false } }
      ],
      series: [
        { name: '国内贷款', type: 'bar', stack: '资金', data: f.domestic, itemStyle: { color: C.primary }, barWidth: 26 },
        { name: '自筹资金', type: 'bar', stack: '资金', data: f.self, itemStyle: { color: C.primary2 } },
        { name: '定金及预收款', type: 'bar', stack: '资金', data: f.deposit, itemStyle: { color: C.teal } },
        { name: '个人按揭贷款', type: 'bar', stack: '资金', data: f.mortgage, itemStyle: { color: C.accent } },
        { name: '到位资金总额', type: 'line', data: f.total, itemStyle: { color: '#1f2a44' }, lineStyle: { width: 2.5 }, symbol: 'circle', symbolSize: 7 }
      ]
    });
    return chart;
  }

  /* ===== 7. 70城房价环比 ===== */
  function chartPrice70() {
    var chart = init('chart-price70'); if (!chart) return;
    var p = D.price70;
    var months = p.months;
    chart.setOption({
      tooltip: { trigger: 'axis', valueFormatter: function (v) { return v + '%'; }  },
      legend: { data: ['新房·一线', '新房·二线', '新房·三线', '二手·一线', '二手·二线', '二手·三线'], top: 0 },
      grid: { left: 50, right: 30, top: 50, bottom: 30 },
      xAxis: { type: 'category', data: months },
      yAxis: { type: 'value', name: '环比%', axisLabel: { formatter: '{value}%' } },
      series: [
        { name: '新房·一线', type: 'line', data: p.newHouse.tier1, itemStyle: { color: C.up }, lineStyle: { width: 2.5 }, symbol: 'circle', symbolSize: 7 },
        { name: '新房·二线', type: 'line', data: p.newHouse.tier2, itemStyle: { color: '#ff8a5b' }, lineStyle: { width: 2 }, symbol: 'circle', symbolSize: 6 },
        { name: '新房·三线', type: 'line', data: p.newHouse.tier3, itemStyle: { color: '#ffb088' }, lineStyle: { width: 2 }, symbol: 'circle', symbolSize: 6 },
        { name: '二手·一线', type: 'line', data: p.secondHand.tier1, itemStyle: { color: C.primary }, lineStyle: { width: 2.5 }, symbol: 'diamond', symbolSize: 7 },
        { name: '二手·二线', type: 'line', data: p.secondHand.tier2, itemStyle: { color: C.teal }, lineStyle: { width: 2 }, symbol: 'diamond', symbolSize: 6 },
        { name: '二手·三线', type: 'line', data: p.secondHand.tier3, itemStyle: { color: C.purple }, lineStyle: { width: 2 }, symbol: 'diamond', symbolSize: 6 }
      ]
    });
    return chart;
  }

  /* ===== 8. 房企TOP10（2026年1-7月累计 + 单月环比+同比）===== */
  function chartDevelopers() {
    var chart = init('chart-developers'); if (!chart) return;
    var list = D.developers.top10 || [];
    var names = list.map(function (d) { return d.name; });

    // 动态计算各项数据
    var cum7 = list.map(function (d) { return d.cum7; });
    var amountJul = list.map(function (d) { return d.cum7 - d.cum6; }); // 7月单月
    var amountJun = list.map(function (d) { return d.cum6 - d.cum5; }); // 6月单月
    var amountJul25 = list.map(function (d) { return d.cum7_25 - d.cum6_25; }); // 2025年7月单月

    // 环比 = (7月单月 - 6月单月) / 6月单月
    var mom = list.map(function (d, i) {
      if (amountJun[i] === 0) return null;
      return ((amountJul[i] - amountJun[i]) / amountJun[i]) * 100;
    });

    // 单月同比 = (2026年7月单月 - 2025年7月单月) / 2025年7月单月
    var yoy = list.map(function (d, i) {
      if (amountJul25[i] === 0) return null;
      return ((amountJul[i] - amountJul25[i]) / amountJul25[i]) * 100;
    });

    var colors = list.map(function (d) {
      return d.cum7 >= 1500 ? C.accent : C.primary;
    });

    chart.setOption({
      tooltip: {
        trigger: 'axis', axisPointer: { type: 'cross', crossStyle: { color: '#5a6580' } },
        formatter: function (ps) {
          var idx = ps[0].dataIndex;
          var d = list[idx];
          var cumTxt = d.cum7 + ' 亿元';
          var julTxt = amountJul[idx].toFixed(1) + ' 亿元';
          var momTxt = mom[idx] == null ? '—' : (mom[idx] >= 0 ? '+' : '') + mom[idx].toFixed(1) + '%';
          var yoyTxt = yoy[idx] == null ? '—' : (yoy[idx] >= 0 ? '+' : '') + yoy[idx].toFixed(1) + '%';
          var momColor = mom[idx] != null && mom[idx] >= 0 ? C.up : C.down;
          var yoyColor = yoy[idx] != null && yoy[idx] >= 0 ? C.up : C.down;
          
          return d.name +
            '<br/><b>1-7月累计：</b>' + cumTxt +
            '<br/><b>7月单月：</b>' + julTxt +
            '<br/><span style="color:' + momColor + ';font-weight:700">环比：' + momTxt + '</span>' +
            '<br/><span style="color:' + yoyColor + ';font-weight:700">单月同比：' + yoyTxt + '</span>';
        }
      },
      legend: { data: ['1-7月累计销售额', '7月单月销售额', '单月环比增速', '单月同比增速'], top: 0  },
      grid: { left: 50, right: 70, top: 40, bottom: 50 },
      xAxis: { type: 'category', data: names, axisLabel: { interval: 0, rotate: 0 } },
      yAxis: [
        { type: 'value', name: '金额(亿元)', axisLabel: { formatter: '{value}' } },
        { type: 'value', name: '增速(%)', axisLabel: { formatter: '{value}%' }, splitLine: { show: false } }
      ],
      series: [
        {
          name: '1-7月累计销售额', type: 'bar',
          data: cum7.map(function (v, i) { return { value: v, itemStyle: { color: colors[i] } }; }),
          barWidth: 30,
          label: { show: true, position: 'top', formatter: function (p) { return cum7[p.dataIndex] + ''; }, fontSize: 15, fontWeight: 600 }
        },
        {
          name: '7月单月销售额', type: 'bar', barGap: '10%',
          data: amountJul.map(function (v) { return { value: v, itemStyle: { color: C.bar2 } }; }),
          barWidth: 20,
          label: { show: true, position: 'top', formatter: function (p) { return amountJul[p.dataIndex].toFixed(0) + ''; }, fontSize: 15, color: '#0d1729' }
        },
        {
          name: '单月环比增速', type: 'line', yAxisIndex: 1,
          data: mom,
          itemStyle: { color: C.accent },
          lineStyle: { width: 2.5, type: 'solid' },
          symbol: 'diamond', symbolSize: 8,
          label: {
            show: true, position: 'top',
            formatter: function (p) { return p.value == null ? '' : (p.value >= 0 ? '+' : '') + p.value.toFixed(1) + '%'; },
            fontSize: 15, color: '#f59e0b', fontWeight: 600
          },
          markLine: {
            silent: true, symbol: 'none',
            lineStyle: { color: '#9aa9c4', type: 'dashed', width: 1.5 },
            data: [{ yAxis: 0 }]
          }
        },
        {
          name: '单月同比增速', type: 'line', yAxisIndex: 1,
          data: yoy,
          itemStyle: { color: C.up },
          lineStyle: { width: 2.5, type: 'dashed' },
          symbol: 'circle', symbolSize: 8,
          label: {
            show: true, position: 'top',
            formatter: function (p) { return p.value == null ? '' : (p.value >= 0 ? '+' : '') + p.value.toFixed(1) + '%'; },
            fontSize: 15, color: '#dc2626', fontWeight: 600
          }
        }
      ]
    });
    return chart;
  }

  function renderAll() {
    renderCumMetrics();
    renderMetrics();
    var charts = [
      chartInvestment(), chartSales(), chartSalesMoM(), chartInventory(),
      chartConstruction(), chartFunding(), chartPrice70(), chartDevelopers()
    ];
    // 响应式
    window.addEventListener('resize', function () {
      charts.forEach(function (c) { if (c) c.resize(); });
    });
  }

  window.Charts = { render: renderAll };
})();