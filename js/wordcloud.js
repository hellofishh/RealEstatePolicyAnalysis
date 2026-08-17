/**
 * 关键词词云渲染（基于 wordcloud2.js）
 * - 确定性布局，所有关键词每次都显示
 * - 悬停显示：出现频次 + 关联政策列表
 */
(function () {
  // 确定性颜色映射：基于词语哈希取固定颜色
  var palette = [
    '#FF6B9D', '#FF8A5C', '#FFD93D', '#6BCB77',
    '#4D96FF', '#9B59B6', '#E84393', '#00D2D3',
    '#FF6348', '#A29BFE', '#FD79A8', '#55E6C1',
    '#F368E0', '#48DBFB', '#FF9FF3', '#FECA57'
  ];

  function hashStr(str) {
    var h = 0;
    for (var i = 0; i < str.length; i++) {
      h = ((h << 5) - h + str.charCodeAt(i)) | 0;
    }
    return Math.abs(h);
  }

  // 构建词云条目：[word, weight, keywordObj]
  // 用 keywordObj 传递 policies 信息到 hover 回调
  var rawList = window.KEYWORDS || [];
  var list = rawList.map(function (k) {
    return [k.name, k.value, k];
  });

  // 计算每个词的稳定颜色（基于名字哈希）
  var colorMap = {};
  rawList.forEach(function (k, i) {
    // 高权重词用前 4 种暖色，中等用中间 8 种，低权重用后 4 种
    var idx;
    if (k.value >= 75) {
      idx = hashStr(k.name) % 4;
    } else if (k.value >= 55) {
      idx = 4 + (hashStr(k.name) % 8);
    } else {
      idx = 12 + (hashStr(k.name) % 4);
    }
    colorMap[k.name] = palette[idx];
  });

  function render() {
    var canvas = document.getElementById('wordcloudCanvas');
    if (!canvas || typeof WordCloud === 'undefined') return;

    WordCloud(canvas, {
      list: list,
      // 紧凑网格
      gridSize: 4,
      // 适度的大小对比（幂次曲线但降低上限，确保所有词都能放下）
      weightFactor: function (size) {
        var ratio = size / 90;
        return Math.max(14, Math.pow(ratio, 1.8) * 80);
      },
      // 粗壮黑体
      fontFamily: '"Noto Sans SC Black", "PingFang SC Heavy", "Microsoft YaHei", "SimHei", "Heiti SC", "Source Han Sans CN Black", "Helvetica Neue", Impact, sans-serif',
      fontWeight: '900',
      // 确定性颜色
      color: function (word, weight) {
        return colorMap[word] || palette[hashStr(word) % palette.length];
      },
      backgroundColor: 'transparent',
      rotateRatio: 0.45,
      rotationSteps: 4,
      minRotation: -Math.PI / 4,
      maxRotation: Math.PI / 4,
      // 确定性布局：不打乱顺序，每次布局完全一致
      shuffle: false,
      drawOutOfBound: false,
      hover: function (item, dim, evt) {
        var tip = document.getElementById('wordcloudTip');
          if (item && item.length >= 3) {
            var kw = item[2];
            var policies = kw.policies || [];
            var count = policies.length;
            var policyNames = policies.map(function (p) { return p.title; }).join('、');
            var html = '<strong>' + kw.name + '</strong>  ·  权重 ' + kw.value + '  ·  涉及 <strong>' + count + '</strong> 项政策';
            if (count > 0) {
              html += '<br/><span style="color:#4a5568">关联政策：' + policyNames + '</span>';
            }
            tip.innerHTML = html;
            canvas.style.cursor = 'pointer';
          } else if (item) {
            tip.innerHTML = '<strong>' + item[0] + '</strong> · 权重 ' + item[1];
            canvas.style.cursor = 'pointer';
          } else {
            tip.textContent = '鼠标悬停关键词查看详情：权重 / 关联政策';
            canvas.style.cursor = 'default';
          }
      },
      click: function (item) {
        if (!item) return;
        var tip = document.getElementById('wordcloudTip');
        tip.textContent = '已选中：' + item[0];
      }
    });
  }

  // 重绘（确保 resize 后也全部显示）
  var resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(render, 300);
  });

  window.WordCloudChart = { render: render };
})();
