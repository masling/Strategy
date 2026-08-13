# 个股操盘代码过滤 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在个股操盘模块中按股票代码或名称过滤可选股票。

**Architecture:** 保持 `state.report.stocks` 为唯一数据源。输入事件更新下拉框的可见选项，只有下拉框的 change 事件才调用现有的 `selectStock`，从而不扰动当前图表和交易明细。

**Tech Stack:** 原生 HTML、CSS、ES modules。

## Global Constraints

- 不新增依赖或行情请求。
- 过滤大小写不敏感，并同时匹配代码与中文名称。
- 无结果时显示不可选的“无匹配股票”。

---

### Task 1: 股票筛选与选择器联动

**Files:**

- Modify: `MQT/Backtest-analyzer/src/index.html:88`
- Modify: `MQT/Backtest-analyzer/src/app.mjs:250-253,374`
- Modify: `MQT/Backtest-analyzer/src/styles.css`

**Interfaces:**

- Consumes: `state.report.stocks`，每项含 `code`、`name`、`trades`。
- Produces: `filteredStocks(query)` 与 `populateStockSelect()`。

- [ ] **Step 1: 加入搜索输入框**

  ```html
  <label class="stock-picker">筛选
    <input id="stockFilterInput" type="search" placeholder="输入代码或名称" autocomplete="off">
  </label>
  ```

- [ ] **Step 2: 实现不区分大小写的代码/名称匹配**

  ```js
  function filteredStocks(query = $('#stockFilterInput').value) {
    const keyword = String(query || '').trim().toUpperCase();
    return (state.report?.stocks || []).filter(stock =>
      !keyword || `${stock.code || ''} ${stock.name || ''}`.toUpperCase().includes(keyword)
    );
  }
  ```

- [ ] **Step 3: 用筛选结果重绘下拉框，并在无结果时显示不可选提示**

- [ ] **Step 4: 绑定输入事件；只重绘选项，不调用 `selectStock`**

  ```js
  $('#stockFilterInput').addEventListener('input', populateStockSelect);
  ```

- [ ] **Step 5: 验证**

  在 `MQT/Backtest-analyzer` 运行 `npm test && npm run build`。载入示例日志后，以 `600183` 和“生益”验证代码/名称筛选；以无匹配字符验证提示；清空验证全部股票恢复；选择股票验证图表和账本切换。

- [ ] **Step 6: 提交**

  ```bash
  git add MQT/Backtest-analyzer/src/index.html MQT/Backtest-analyzer/src/app.mjs MQT/Backtest-analyzer/src/styles.css
  git commit -m "支持个股代码过滤"
  ```
