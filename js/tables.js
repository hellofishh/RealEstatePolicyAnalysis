/**
 * 数据表格渲染（单月数据 + 环比）
 */
(function () {
  var D = window.SALES_DATA || {};
  var periods = D.periods || [];

  function fmt(n, fix) {
    if (n == null) return '—';
    return fix != null ? Number(n).toFixed(fix) : n.toLocaleString('zh-CN');
  }
  function pct(v) { return v == null ? '—' : (v >= 0 ? '+' : '') + v + '%'; }
  function cls(v) {
    if (v == null) return '';
    return v >= 0 ? 'pos' : 'neg';
  }
  function th(label) { return '<th>' + label + '</th>'; }
  function td(v, fix, colorV) {
    var c = colorV != null ? cls(colorV) : '';
    return '<td class="' + c + '">' + fmt(v, fix) + '</td>';
  }

  function buildTable(headers, rows) {
    var html = '<table class="data-table"><thead><tr>';
    headers.forEach(function (h) { html += th(h); });
    html += '</tr></thead><tbody>';
    rows.forEach(function (r) {
      html += '<tr>';
      r.forEach(function (cell) {
        if (typeof cell === 'object' && cell !== null) {
          html += '<td class="' + (cell.cls || '') + '">' + cell.val + '</td>';
        } else {
          html += '<td>' + cell + '</td>';
        }
      });
      html += '</tr>';
    });
    html += '</tbody></table>';
    return html;
  }

  function tableInvestment() {
    var inv = D.investment;
    var headers = ['月份', '投资总额(亿元)', '总额环比', '住宅投资', '住宅环比', '办公楼投资', '办公环比', '商业用房投资', '商业环比'];
    var rows = periods.map(function (p, i) {
      return [
        p, inv.total[i], { val: pct(inv.mom.total[i]), cls: cls(inv.mom.total[i]) },
        inv.residential[i], { val: pct(inv.mom.residential[i]), cls: cls(inv.mom.residential[i]) },
        inv.office[i], { val: pct(inv.mom.office[i]), cls: cls(inv.mom.office[i]) },
        inv.commercial[i], { val: pct(inv.mom.commercial[i]), cls: cls(inv.mom.commercial[i]) }
      ];
    });
    return buildTable(headers, rows);
  }

  function tableSales() {
    var s = D.sales;
    var headers = ['月份', '销售面积(万㎡)', '面积环比', '销售额(亿元)', '金额环比', '住宅面积', '住宅面积环比', '住宅金额', '住宅金额环比'];
    var rows = periods.map(function (p, i) {
      return [
        p, s.area[i], { val: pct(s.mom.area[i]), cls: cls(s.mom.area[i]) },
        s.amount[i], { val: pct(s.mom.amount[i]), cls: cls(s.mom.amount[i]) },
        fmt(s.residentialArea[i]), { val: pct(s.mom.residentialArea[i]), cls: cls(s.mom.residentialArea[i]) },
        fmt(s.residentialAmount[i]), { val: pct(s.mom.residentialAmount[i]), cls: cls(s.mom.residentialAmount[i]) }
      ];
    });
    return buildTable(headers, rows);
  }

  function tableConstruction() {
    var c = D.construction;
    var headers = ['月份', '新开工(万㎡)', '新开工环比', '竣工(万㎡)', '竣工环比', '施工面积(万㎡)', '施工环比'];
    var rows = periods.map(function (p, i) {
      return [
        p, c.newStart[i], { val: pct(c.mom.newStart[i]), cls: cls(c.mom.newStart[i]) },
        c.complete[i], { val: pct(c.mom.complete[i]), cls: cls(c.mom.complete[i]) },
        c.construction[i], { val: pct(c.mom.construction[i]), cls: cls(c.mom.construction[i]) }
      ];
    });
    return buildTable(headers, rows);
  }

  function tableFunding() {
    var f = D.funding;
    var headers = ['月份', '到位资金(亿元)', '总额环比', '国内贷款', '贷款环比', '自筹资金', '自筹环比', '定金及预收款', '定金环比', '个人按揭', '按揭环比'];
    var rows = periods.map(function (p, i) {
      return [
        p, f.total[i], { val: pct(f.mom.total[i]), cls: cls(f.mom.total[i]) },
        f.domestic[i], { val: pct(f.mom.domestic[i]), cls: cls(f.mom.domestic[i]) },
        f.self[i], { val: pct(f.mom.self[i]), cls: cls(f.mom.self[i]) },
        f.deposit[i], { val: pct(f.mom.deposit[i]), cls: cls(f.mom.deposit[i]) },
        f.mortgage[i], { val: pct(f.mom.mortgage[i]), cls: cls(f.mom.mortgage[i]) }
      ];
    });
    return buildTable(headers, rows);
  }

  var builders = {
    investment: tableInvestment,
    sales: tableSales,
    construction: tableConstruction,
    funding: tableFunding
  };

  function switchTo(key) {
    var container = document.getElementById('tableContainer');
    if (!container) return;
    var fn = builders[key];
    if (!fn) return;
    var tableHtml = fn();
    container.innerHTML = tableHtml +
      '<p class="table-source">数据来源：国家统计局《全国房地产开发和销售情况》月度新闻稿。数据为单月值；环比基于相邻月份计算。</p>';
  }

  function bindTabs() {
    var tabs = document.getElementById('tableTabs');
    if (!tabs) return;
    tabs.addEventListener('click', function (e) {
      var btn = e.target.closest('.tab-btn');
      if (!btn) return;
      tabs.querySelectorAll('.tab-btn').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      switchTo(btn.getAttribute('data-table'));
    });
  }

  window.Tables = {
    render: function () { bindTabs(); switchTo('investment'); }
  };
})();