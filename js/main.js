/**
 * 应用入口：DOM 就绪后渲染所有模块
 */
(function () {
  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {
    // 政策时间线
    if (window.Timeline) window.Timeline.render();
    // 词云
    if (window.WordCloudChart) window.WordCloudChart.render();
    // 图表
    if (window.Charts) window.Charts.render();
    // 表格
    if (window.Tables) window.Tables.render();
  });
})();
