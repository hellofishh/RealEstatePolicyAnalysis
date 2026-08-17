/**
 * 政策时间线渲染
 * - 按时间正序展示政策卡片
 * - 支持按类别筛选
 * - 点击卡片展开核心观点与对比分析
 */
(function () {
  var Policies = window.POLICIES || [];
  // 按日期升序排序
  Policies = Policies.slice().sort(function (a, b) {
    return new Date(a.date) - new Date(b.date);
  });

  // 类别列表（去重，保持出现顺序）
  var categories = [];
  Policies.forEach(function (p) {
    if (categories.indexOf(p.category) === -1) categories.push(p.category);
  });

  function formatDateParts(dateStr) {
    var d = new Date(dateStr);
    var month = (d.getMonth() + 1).toString();
    var day = d.getDate().toString();
    return { day: day, month: month + '月' };
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // 重点关键词库（按长度排序，避免短词先匹配）
  var HIGHLIGHT_KEYWORDS = [
    '金融资产属性', '存量商品房收储', '存量房贷利率下调', '综合融资成本',
    '保障性住房', '深化住房公积金制度改革', '房地产独立成章',
    '3000亿元', '专项再贷款', '保交房白名单', '项目公司制',
    '主办银行制', '现房销售', '住房公积金', '首付15%',
    '存量时代', '二手房占比', '存量提质', '去库存',
    '新发展模式', '租购并举', '因城施策', '预期管理',
    '扩大消费', '耐用消费品', '安全屏障', '两重两新',
    '金融资产', '税收减免', '增值税', '个贷',
    '降杠杆', '去杠杆', '稳预期', '盘活存量',
    '城市更新', '城中村改造', '保障性',
    '重大战略', '重点领域', '精细化运营', '存量资产盘活',
    '首次', '首次写入', '里程碑', '关键', '核心',
    '重大', '重要', '首个', '第一部',
    '全国统一', '全面', '系统性', '历史性',
    '控增量', '优供给', '着力稳定', '修复居民资产负债表',
    '好房子', '投资品', '消费品',
    '国务院常务会议', '决定草案', '扩面提质', '公积金改革',
    '审议通过', '修订草案', '扩面', '提质',
  ];

  // 转义正则特殊字符
  function escapeRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  /**
   * 将文本中的关键词用高亮样式包裹
   * @param {string} text 原始文本（已 HTML 转义）
   * @returns {string} 高亮后的 HTML
   */
  function highlightText(text) {
    if (!text) return '';
    // 按长度降序排列关键词，避免短词先匹配长词
    var sorted = HIGHLIGHT_KEYWORDS.slice().sort(function (a, b) { return b.length - a.length; });
    // 构建正则：用 | 连接所有关键词
    var pattern = new RegExp('(' + sorted.map(escapeRegex).join('|') + ')', 'g');
    return text.replace(pattern, '<span class="hl">$1</span>');
  }

  function renderItem(p) {
    var parts = formatDateParts(p.date);
    var pointsHtml = p.points.map(function (pt) {
      return '<li>' + highlightText(escapeHtml(pt)) + '</li>';
    }).join('');
    var sourceHost = '';
    try { sourceHost = new URL(p.url).hostname.replace(/^www\./, ''); } catch (e) {}

    return (
      '<div class="policy-item" data-category="' + escapeHtml(p.category) + '">' +
        '<div class="policy-card">' +
          '<div class="policy-head" data-toggle="1">' +
            '<div class="policy-date">' +
              '<div class="d-day">' + parts.day + '</div>' +
              '<div class="d-month">' + parts.month + '</div>' +
            '</div>' +
            '<div class="policy-main">' +
              '<div class="policy-name">' + escapeHtml(p.name) + '</div>' +
              '<div class="policy-meta">' +
                '<span class="tag tag-agency">' + escapeHtml(p.agency) + '</span>' +
                '<span class="tag tag-category">' + escapeHtml(p.category) + '</span>' +
                '<a class="policy-source" href="' + escapeHtml(p.url) + '" target="_blank" rel="noopener" onclick="event.stopPropagation()">🔗 来源：' + escapeHtml(sourceHost) + '</a>' +
              '</div>' +
            '</div>' +
            '<span class="toggle-icon">▼</span>' +
          '</div>' +
          '<div class="policy-body"><div class="policy-body-inner">' +
            '<div class="policy-section-label">📝 核心观点</div>' +
            '<ul class="policy-points">' + pointsHtml + '</ul>' +
            '<div class="policy-section-label">🔍 与之前政策对比分析</div>' +
            '<div class="policy-compare">' + highlightText(escapeHtml(p.comparison)) + '</div>' +
          '</div></div>' +
        '</div>' +
      '</div>'
    );
  }

  function renderFilter() {
    var bar = document.getElementById('policyFilter');
    var html = '<button class="filter-btn active" data-cat="all">全部 (' + Policies.length + ')</button>';
    categories.forEach(function (cat) {
      var count = Policies.filter(function (p) { return p.category === cat; }).length;
      html += '<button class="filter-btn" data-cat="' + escapeHtml(cat) + '">' + escapeHtml(cat) + ' (' + count + ')</button>';
    });
    bar.innerHTML = html;
    bar.addEventListener('click', function (e) {
      var btn = e.target.closest('.filter-btn');
      if (!btn) return;
      bar.querySelectorAll('.filter-btn').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      var cat = btn.getAttribute('data-cat');
      document.querySelectorAll('.policy-item').forEach(function (it) {
        it.style.display = (cat === 'all' || it.getAttribute('data-category') === cat) ? '' : 'none';
      });
    });
  }

  function renderTimeline() {
    var box = document.getElementById('policyTimeline');
    box.innerHTML = Policies.map(renderItem).join('');
    box.addEventListener('click', function (e) {
      var head = e.target.closest('[data-toggle]');
      if (!head) return;
      head.closest('.policy-item').classList.toggle('expanded');
    });
  }

  window.Timeline = { render: function () { renderFilter(); renderTimeline(); } };
})();
