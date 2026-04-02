---
site: chinastarpa88.com
script: chinastarpa88.py
date: 2026-04-02
status: completed
data_extracted: 餐厅菜单：4 大类、27 分组、409 菜品，含名称、价格、描述
---

## 探索阶段

### 数据来源

- **站点特征**: Next.js SPA，基于 BeyondMenu 平台（实体 ID: 36519）
- **首页 URL**: `https://www.chinastarpa88.com/`
- **菜单 URL**: `https://www.chinastarpa88.com/ji5od7sj/china-star-blue-bell-19422/order-online#menu-section`
- **数据位置**: Next.js streaming chunks (`self.__next_f.push`) 中嵌入的 `menuCategories` JSON 数组
- **提取方式**: 正则匹配 `self.__next_f.push([1,"..."])` chunks → 找到含 `menuCatId` 的 chunk → unicode_escape 解码 → 提取 `menuCategories` 数组 → JSON 解析
- **数据路径**: `menuCategories[].menuGroups[].menuItems[]`，每个 item 含 `menuItemName`、`menuItemPrice`、`menuItemDesc`

### 探索中遇到的问题（每次迭代实时追加）
| # | 问题 | 现象 | 排查过程 | 处理方式 |
|---|------|------|---------|---------|
| 1 | 首页无菜单数据 | 首页 HTML 中无菜单内容 | 检查 `__NEXT_DATA__`、JSON-LD，发现 `hasMenu` 指向订单页 | 通过 JSON-LD `hasMenu` 字段和首页 "View Menu" 链接定位到 BeyondMenu 订单页 |
| 2 | DOM 虚拟化导致数据不全 | 只能获取首分类 ~64 个菜品 | 点击分类标签触发懒加载，但虚拟化渲染导致超时 | 放弃 DOM 遍历，改用解析 Next.js streaming chunk 中的嵌入数据 |
| 3 | BeyondMenu API 未直接暴露 | 未找到独立的 JSON API 端点 | 通过 session.py 网络监听捕获 | 数据直接在 HTML streaming chunks 中，无需额外 API 调用 |

## 开发阶段

### 确认的 API 端点
| 端点关键词 | 用途 | 数据路径 |
|-----------|------|---------|
| `self.__next_f.push` (HTML 内嵌) | Next.js streaming data | `menuCategories[].menuGroups[].menuItems[]` |

### 开发中遇到的坑
1. **Unicode 编码** — chunk 中的数据使用 unicode escapes（如 `\u0022` 表示引号），需先 `encode().decode('unicode_escape')` 再 JSON 解析
2. **Item 计数 bug** — 初始代码用 `len(item)` 计算菜品数（item 是 dict，返回 key 数量），改为 `1` 计数
3. **Text 输出污染** — 首次测试 text 格式时 nodriver cleanup 消息混入 stdout，确认 cleanup 抑制代码在 `print()` 之后执行

### 价格/数字字段格式
- 价格格式：字符串，直接显示美元金额（如 `27`、`13.95`），无美分转换
- 特殊字段：部分菜品含 `menuItemDesc` 描述

## 可复用模式
- **探索发现**: BeyondMenu 平台的餐厅站点，菜单数据嵌入在 Next.js streaming chunks 中
- **开发经验**: Next.js 站点优先检查 `self.__next_f.push` chunks，比 DOM 遍历更可靠、更高效
- **URL 映射**: 首页 → 订单页的映射通过 JSON-LD `hasMenu` 和首页 "View Menu" 链接发现

## 中文乱码修复记录

### 根因分析
在 `self.__next_f.push([1,"DATA"])` 的 DATA 部分中，**中文以原始 UTF-8 字节存储**，而**引号以 `\"` 转义**。

使用 `.encode().decode('unicode_escape')` 会把 UTF-8 字节重新编码为 Latin-1 码位，导致中文变成乱码（如 `鸡翅` → `é¸¡`）。

### 修复方案
1. **不用 `unicode_escape`**，改用自定义提取器：手动扫描 `self.__next_f.push([1,"` 和结束 `" ]`，跳过转义字符
2. **只替换 `\"` 为 `"`**，保留原始 UTF-8 中文字符
3. **直接提取 `menuCategories` 数组**，不解析整个 JSON 对象（因为外层包含前缀如 `6:`）

```python
def _extract_push_data(self, html: str) -> List[str]:
    """手动提取 push 数据，处理嵌套转义引号"""
    marker = 'self.__next_f.push([1,"'
    # 扫描匹配，跳过 \" 转义
    ...

def _decode_chunk(self, chunk: str) -> str:
    """只替换转义引号，保留 UTF-8 中文"""
    return chunk.replace('\\"', '"')

def _parse_menu_from_page(self, html: str) -> List[Dict]:
    """直接定位 menuCategories 数组并解析"""
    mc_pos = decoded.find('"menuCategories"')
    arr_start = decoded.find('[', mc_pos)
    # 括号匹配找到数组结束位置
    ...
```

### 关键教训
- `unicode_escape` 会破坏 UTF-8 多字节字符，只对纯 ASCII + `\uXXXX` 转义安全
- 当数据中同时存在原始 UTF-8 和 `\"` 转义时，需要自定义解码逻辑
- Next.js streaming chunks 的数据结构可能包含前缀（如 `6:`），需要先找到 JSON 数组再解析
