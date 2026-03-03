# 无工厂模式电商带货供应链 SOP

> 文档版本：v1.0  
> 更新时间：2026-03-02  
> 适用模式：一件代发、分销、OEM/ODM、无货源电商

---

## 一、无工厂模式概述

### 1.1 模式定义

**无工厂模式** = 轻资产运营 + 供应链整合 + 品牌/渠道运营

核心特点：
- ✅ 不持有生产设施
- ✅ 不持有大量库存
- ✅ 专注选品、营销、客户服务
- ✅ 依赖供应商网络完成生产和履约

### 1.2 常见模式对比

| 模式 | 库存 | 发货 | 品牌 | 利润率 | 风险 | 适合场景 |
|------|------|------|------|--------|------|----------|
| **一件代发** | 无库存 | 供应商直发 | 供应商品牌 | 15-30% | 低 | 新手起步、测款 |
| **分销模式** | 少量库存 | 自建仓/供应商 | 混合 | 20-40% | 中 | 有一定销量基础 |
| **OEM/ODM** | 按需备货 | 自建仓/第三方 | 自有品牌 | 30-60% | 中高 | 品牌化运营 |
| **无货源电商** | 无库存 | 供应商直发 | 供应商品牌 | 10-25% | 低 | 平台店群运营 |

---

## 二、供应链整合 SOP

### 2.1 供应商开发 SOP

#### 阶段一：供应商寻源（持续进行）

```
┌─────────────────────────────────────────────────────────────────────┐
│                        供应商寻源流程                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  渠道 1: 线上平台                                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ • 1688 阿里巴巴（国内批发）                                   │    │
│  │ • 义乌购（小商品）                                           │    │
│  │ • 慧聪网（工业品）                                           │    │
│  │ • 中国制造网（出口导向）                                     │    │
│  │ • 全球资源（Global Sources）                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  渠道 2: 产业带实地考察                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ • 广州/深圳（3C 电子、服装）                                  │    │
│  │ • 义乌（小商品、饰品）                                       │    │
│  │ • 泉州/晋江（鞋服）                                          │    │
│  │ • 佛山（家具、建材）                                         │    │
│  │ • 宁波（家电、模具）                                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  渠道 3: 行业展会                                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ • 广交会（综合）                                             │    │
│  │ • 华东进出口商品交易会                                       │    │
│  │ • 各行业专业展会                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  渠道 4: 供应商推荐                                                  │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ • 现有供应商推荐同行                                         │    │
│  │ • 行业协会推荐                                               │    │
│  │ • 电商平台官方供应商库                                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 供应商筛选标准

| 评估维度 | 权重 | 评估指标 | 合格标准 |
|----------|------|----------|----------|
| **资质认证** | 20% | 营业执照、生产许可证、质量体系认证 | 三证齐全、ISO9001 优先 |
| **生产能力** | 25% | 日产能、交期、设备水平 | 日产能≥1000 件、交期≤7 天 |
| **产品质量** | 25% | 次品率、退货率、质检报告 | 次品率<2%、退货率<3% |
| **价格竞争力** | 15% | 出厂价、MOQ、账期 | 低于市场均价 5-10% |
| **配合度** | 15% | 响应速度、定制能力、售后服务 | 2 小时内响应、支持小单定制 |

#### 供应商开发 API 集成

```javascript
// 1688 开放平台 API
const api1688 = {
  // 商品搜索
  search: {
    endpoint: '/api/offer/search',
    method: 'GET',
    params: {
      q: '关键词',
      beginPrice: 0,
      endPrice: 100,
      beginQuantity: 1,
      endQuantity: 1000
    }
  },
  
  // 商品详情
  detail: {
    endpoint: '/api/offer/detail',
    method: 'GET',
    params: {
      offerId: '商品 ID'
    }
  },
  
  // 供应商信息
  supplier: {
    endpoint: '/api/supplier/info',
    method: 'GET',
    params: {
      memberIds: '供应商 ID'
    }
  },
  
  // 一键铺货
  distribute: {
    endpoint: '/api/distribute/push',
    method: 'POST',
    params: {
      offerId: '商品 ID',
      targetPlatform: 'taobao|douyin|kuaishou'
    }
  }
};

// 抖音选品中心 API
const apiDouyinSelection = {
  // 选品池查询
  pool: {
    endpoint: '/api/selection/pool/list',
    method: 'GET',
    params: {
      category: '类目 ID',
      priceRange: '价格区间',
      commissionRate: '佣金比例'
    }
  },
  
  // 商品详情
  product: {
    endpoint: '/api/selection/product/detail',
    method: 'GET',
    params: {
      productId: '商品 ID'
    }
  },
  
  // 添加橱窗
  addWindow: {
    endpoint: '/api/selection/product/add',
    method: 'POST',
    params: {
      productId: '商品 ID',
      authorId: '达人 ID'
    }
  }
};
```

---

### 2.2 供应商评估 SOP

#### 评估流程

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   初步筛选   │    │   样品评估   │    │   实地考察   │    │   小单测试   │
│             │    │             │    │             │    │             │
│ • 资质审核  │───▶│ • 样品寄送  │───▶│ • 工厂参观  │───▶│ • 试订单    │
│ • 在线沟通  │    │ • 质量检验  │    │ • 产能评估  │    │ • 履约测试  │
│ • 报价对比  │    │ • 价格确认  │    │ • 管理评估  │    │ • 服务评估  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
  1-2 个工作日        3-5 个工作日        5-7 个工作日        7-14 个工作日
```

#### 样品评估表

| 评估项目 | 评估内容 | 评分标准 | 权重 |
|----------|----------|----------|------|
| 外观质量 | 包装、做工、细节 | 优秀 5 分/良好 3 分/差 1 分 | 20% |
| 功能性能 | 使用效果、稳定性 | 达标 5 分/基本 3 分/不达标 1 分 | 25% |
| 材质用料 | 原材料、环保性 | 优质 5 分/普通 3 分/劣质 1 分 | 20% |
| 性价比 | 价格与质量匹配度 | 高 5 分/中 3 分/低 1 分 | 20% |
| 改进空间 | 可优化程度 | 小 5 分/中 3 分/大 1 分 | 15% |

**合格标准**: 综合评分≥4 分（满分 5 分）

#### 供应商分级管理

| 等级 | 标准 | 合作策略 | 订单占比 |
|------|------|----------|----------|
| **A 级（战略供应商）** | 评分≥4.5，合作≥6 个月 | 深度合作、优先下单、联合开发 | 50-70% |
| **B 级（核心供应商）** | 评分 4.0-4.5，合作≥3 个月 | 稳定合作、定期评估 | 20-40% |
| **C 级（备选供应商）** | 评分 3.5-4.0，新供应商 | 小单测试、观察期 | 10-20% |
| **D 级（淘汰供应商）** | 评分<3.5 或重大违规 | 停止合作、寻找替代 | 0% |

---

### 2.3 选品上架 SOP

#### 无货源模式选品流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                        选品上架全流程                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  步骤 1: 市场洞察（1-2 天）                                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ API: /api/data/trending（ trending 商品查询）                  │    │
│  │ • 平台热销榜分析                                             │    │
│  │ • 社交媒体趋势监测                                           │    │
│  │ • 竞争对手商品监控                                           │    │
│  │ • 季节性需求预测                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                               │                                      │
│                               ▼                                      │
│  步骤 2: 供应商匹配（1-2 天）                                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ API: /api/supplier/search（供应商搜索）                        │    │
│  │ • 1688 商品搜索                                              │    │
│  │ • 价格对比（≥3 家供应商）                                     │    │
│  │ • 库存确认可用性                                             │    │
│  │ • 发货时效确认                                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                               │                                      │
│                               ▼                                      │
│  步骤 3: 利润测算（0.5 天）                                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ 公式：利润 = 售价 - 成本 - 平台佣金 - 运费 - 营销费用          │    │
│  │ • 目标利润率：≥30%                                           │    │
│  │ • 最低利润率：≥20%                                           │    │
│  │ • 盈亏平衡点计算                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                               │                                      │
│                               ▼                                      │
│  步骤 4: 商品上架（0.5 天）                                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ API: /api/product/create（商品创建）                          │    │
│  │ • 标题优化（关键词 + 卖点）                                   │    │
│  │ • 主图/详情页设计                                            │    │
│  │ • 价格策略设置                                               │    │
│  │ • 库存同步（虚拟库存）                                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                               │                                      │
│                               ▼                                      │
│  步骤 5: 推广测试（3-7 天）                                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ API: /api/live/product/add（直播商品添加）                    │    │
│  │ • 小额投放测试                                               │    │
│  │ • 转化率监测                                                 │    │
│  │ • 数据反馈优化                                               │    │
│  │ • 爆款筛选                                                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 商品上架 API 调用序列

```javascript
// 商品上架完整流程
async function productListingFlow(productData) {
  // 1. 查询供应商商品
  const supplierProduct = await api.post('/api/supplier/product/search', {
    keyword: productData.keyword,
    priceRange: productData.priceRange
  });
  
  // 2. 获取商品详情
  const productDetail = await api.get('/api/supplier/product/detail', {
    offerId: supplierProduct.bestMatch.offerId
  });
  
  // 3. 利润测算
  const profitCalc = calculateProfit({
    costPrice: productDetail.price,
    targetPrice: productData.targetPrice,
    platformFee: 0.05, // 5% 平台佣金
    shippingCost: productDetail.shippingFee,
    marketingCost: productData.marketingBudget
  });
  
  if (profitCalc.margin < 0.2) {
    throw new Error('利润率不足 20%，放弃上架');
  }
  
  // 4. 创建本地商品
  const localProduct = await api.post('/api/product/create', {
    name: optimizeTitle(productDetail.name),
    description: productDetail.description,
    images: productDetail.images,
    price: profitCalc.sellingPrice,
    virtualStock: 999, // 虚拟库存
    supplierId: supplierProduct.bestMatch.supplierId,
    supplierOfferId: supplierProduct.bestMatch.offerId
  });
  
  // 5. 同步到销售平台
  const platformSync = await Promise.all([
    syncToDouyin(localProduct),
    syncToKuaishou(localProduct),
    syncToTaobao(localProduct)
  ]);
  
  // 6. 添加到选品池
  await api.post('/api/selection/pool/add', {
    productId: localProduct.id,
    priority: profitCalc.margin > 0.3 ? 'high' : 'normal'
  });
  
  return {
    success: true,
    productId: localProduct.id,
    profitMargin: profitCalc.margin
  };
}
```

---

### 2.4 订单履约 SOP

#### 无货源订单流转

```
┌─────────────────────────────────────────────────────────────────────┐
│                      无货源订单履约流程                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  用户下单                                                            │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  步骤 1: 订单接收（自动）                                      │    │
│  │  API: /api/order/list（ webhook 自动接收）                      │    │
│  │  • 订单信息解析                                               │    │
│  │  • 供应商匹配                                                 │    │
│  │  • 库存确认                                                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  步骤 2: 供应商下单（自动/手动）                               │    │
│  │  API: /api/supplier/order/create（供应商下单）                 │    │
│  │  • 1688 一键下单                                              │    │
│  │  • 收货地址填写（用户地址）                                   │    │
│  │  • 备注信息（不显示价格）                                     │    │
│  │  • 支付货款                                                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  步骤 3: 物流跟踪（自动）                                      │    │
│  │  API: /api/logistics/track（物流跟踪）                         │    │
│  │  • 获取供应商发货单号                                         │    │
│  │  • 同步到销售平台                                             │    │
│  │  API: /api/order/ship（发货通知）                             │    │
│  │  • 物流状态监控                                               │    │
│  │  • 异常预警                                                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  步骤 4: 签收确认（自动）                                      │    │
│  │  API: /api/order/status（订单状态查询）                        │    │
│  │  • 签收状态确认                                               │    │
│  │  • 用户满意度调查                                             │    │
│  │  • 订单完成归档                                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ⏱️ 时效要求：从用户下单到供应商下单 ≤ 2 小时                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 订单自动化处理

```javascript
// 订单自动履约系统
class OrderFulfillmentSystem {
  constructor() {
    this.supplierMapping = new Map(); // 商品 - 供应商映射
    this.autoFulfillEnabled = true;
  }
  
  // 新订单处理
  async handleNewOrder(order) {
    try {
      // 1. 获取供应商信息
      const supplier = await this.getSupplierForProduct(order.items[0].productId);
      
      if (!supplier) {
        throw new Error('未找到对应供应商');
      }
      
      // 2. 检查供应商库存
      const stockCheck = await api.post('/api/supplier/stock/check', {
        supplierId: supplier.id,
        offerId: supplier.offerId,
        quantity: order.items[0].quantity
      });
      
      if (!stockCheck.available) {
        await this.handleStockOut(order, supplier);
        return;
      }
      
      // 3. 向供应商下单
      const supplierOrder = await api.post('/api/supplier/order/create', {
        supplierId: supplier.id,
        offerId: supplier.offerId,
        quantity: order.items[0].quantity,
        shippingAddress: order.shippingAddress,
        buyerMessage: '请勿放价格单，谢谢配合'
      });
      
      // 4. 记录关联关系
      await this.linkOrders(order.id, supplierOrder.id);
      
      // 5. 等待供应商发货
      await this.waitForShipment(supplierOrder.id);
      
    } catch (error) {
      await this.handleFulfillmentError(order, error);
    }
  }
  
  // 物流信息同步
  async syncTrackingInfo(supplierOrderId) {
    const trackingInfo = await api.get('/api/supplier/order/tracking', {
      orderId: supplierOrderId
    });
    
    // 获取关联的用户订单
    const userOrders = await this.getLinkedUserOrders(supplierOrderId);
    
    // 同步到各销售平台
    for (const userOrder of userOrders) {
      await api.post('/api/order/ship', {
        orderId: userOrder.id,
        platform: userOrder.platform,
        trackingNumber: trackingInfo.trackingNumber,
        logisticsCompany: trackingInfo.logisticsCompany
      });
    }
  }
}
```

---

### 2.5 库存管理 SOP

#### 虚拟库存管理

```
┌─────────────────────────────────────────────────────────────────────┐
│                        虚拟库存同步机制                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐ │
│  │  供应商库存   │         │   中台库存    │         │  销售平台库存 │ │
│  │              │         │              │         │              │ │
│  │ • 1688 库存   │────────▶│ • 虚拟库存池  │────────▶│ • 抖音小店    │ │
│  │ • 厂家库存    │  实时   │ • 安全库存    │  实时   │ • 快手小店    │ │
│  │ • 仓库库存    │  同步   │ • 预警阈值    │  同步   │ • 淘宝店铺    │ │
│  └──────────────┘         └──────────────┘         └──────────────┘ │
│         │                       │                       │            │
│         ▼                       ▼                       ▼            │
│  API: /api/supplier/     API: /api/inventory/   API: /api/product/   │
│       stock/query            inventory/sync          stock/update    │
│                                                                      │
│  同步频率：                                                          │
│  • 正常时段：每 30 分钟同步一次                                       │
│  • 直播期间：每 5 分钟同步一次                                        │
│  • 库存预警时：实时同步                                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 库存预警机制

| 预警级别 | 库存比例 | 触发条件 | 应对措施 | API 调用 |
|----------|----------|----------|----------|----------|
| **绿色（正常）** | >50% | - | 正常销售 | - |
| **蓝色（关注）** | 30-50% | 库存下降快 | 关注销量 | `/api/inventory/alert` |
| **黄色（预警）** | 10-30% | 库存不足 | 联系补货 | `/api/supplier/stock/reserve` |
| **橙色（紧张）** | 5-10% | 库存紧张 | 限购/下架 | `/api/product/stock/limit` |
| **红色（缺货）** | <5% | 库存告急 | 立即下架 | `/api/product/stock/set?value=0` |

#### 库存同步 API

```javascript
// 库存同步服务
class InventorySyncService {
  constructor() {
    this.syncInterval = 30 * 60 * 1000; // 30 分钟
    this.liveSyncInterval = 5 * 60 * 1000; // 5 分钟（直播时）
    this.isLive = false;
  }
  
  // 启动同步
  startSync() {
    setInterval(() => this.syncAllProducts(), 
      this.isLive ? this.liveSyncInterval : this.syncInterval);
  }
  
  // 同步所有商品库存
  async syncAllProducts() {
    const products = await api.get('/api/product/list', { status: 'active' });
    
    for (const product of products) {
      try {
        // 获取供应商库存
        const supplierStock = await api.get('/api/supplier/stock/query', {
          supplierId: product.supplierId,
          offerId: product.supplierOfferId
        });
        
        // 计算可销售库存
        const availableStock = this.calculateAvailableStock(
          supplierStock.quantity,
          product.reservedStock,
          product.safetyStock
        );
        
        // 更新销售平台库存
        await api.post('/api/product/stock/update', {
          productId: product.id,
          stock: availableStock,
          platforms: product.platforms
        });
        
        // 检查预警
        await this.checkStockAlert(product, availableStock);
        
      } catch (error) {
        logError(`库存同步失败：${product.id}`, error);
      }
    }
  }
  
  // 库存预警检查
  async checkStockAlert(product, stock) {
    const ratio = stock / product.maxStock;
    
    if (ratio < 0.05) {
      await api.post('/api/inventory/alert', {
        productId: product.id,
        level: 'red',
        message: '库存告急，立即下架',
        action: 'auto_delist'
      });
    } else if (ratio < 0.1) {
      await api.post('/api/inventory/alert', {
        productId: product.id,
        level: 'orange',
        message: '库存紧张，准备下架',
        action: 'notify'
      });
    } else if (ratio < 0.3) {
      await api.post('/api/inventory/alert', {
        productId: product.id,
        level: 'yellow',
        message: '库存预警，联系补货',
        action: 'notify_supplier'
      });
    }
  }
}
```

---

### 2.6 品控管理 SOP

#### 无工厂模式品控流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                        品控管理全流程                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  阶段 1: 供应商准入品控                                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ • 资质审核（营业执照、生产许可证、质检报告）                   │    │
│  │ • 工厂实地考察（生产环境、设备、管理）                         │    │
│  │ • 样品检测（第三方检测机构）                                   │    │
│  │ • 小批量试单（质量稳定性验证）                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                               │                                      │
│                               ▼                                      │
│  阶段 2: 日常品控                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ • 批次抽检（每批次随机抽检 5-10%）                             │    │
│  │ • 用户反馈监测（差评分析、退货原因）                           │    │
│  │ • 定期复检（每季度送检一次）                                   │    │
│  │ • 神秘顾客购买（匿名购买检测）                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                               │                                      │
│                               ▼                                      │
│  阶段 3: 问题处理                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ • 质量问题分级（轻微/一般/严重）                               │    │
│  │ • 供应商沟通整改                                             │    │
│  │ • 批量问题召回                                               │    │
│  │ • 供应商淘汰机制                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 品控指标体系

| 指标 | 计算公式 | 目标值 | 预警值 | 数据来源 |
|------|----------|--------|--------|----------|
| **次品率** | 次品数/总收货数×100% | <2% | >3% | 入库质检 |
| **退货率** | 退货订单数/总订单数×100% | <3% | >5% | 售后系统 |
| **差评率** | 差评数/总评价数×100% | <1% | >2% | 评价系统 |
| **质检合格率** | 合格批次/总批次×100% | >98% | <95% | 质检报告 |
| **客诉响应时效** | 平均响应时间 | <2 小时 | >4 小时 | 客服系统 |

#### 品控 API 集成

```javascript
// 品控管理系统
class QualityControlSystem {
  // 批次质检记录
  async recordInspection(batchData) {
    const inspection = await api.post('/api/qc/inspection/create', {
      batchId: batchData.batchId,
      supplierId: batchData.supplierId,
      productId: batchData.productId,
      sampleSize: batchData.sampleSize,
      defectiveCount: batchData.defectiveCount,
      inspectionDate: new Date(),
      inspector: batchData.inspector,
      result: batchData.defectiveCount / batchData.sampleSize < 0.02 ? 'pass' : 'fail'
    });
    
    // 如果不合格，触发预警
    if (inspection.result === 'fail') {
      await api.post('/api/qc/alert', {
        batchId: batchData.batchId,
        level: 'warning',
        message: '批次质检不合格，暂停收货'
      });
      
      // 冻结该批次商品
      await api.post('/api/product/stock/freeze', {
        batchId: batchData.batchId
      });
    }
    
    return inspection;
  }
  
  // 用户反馈分析
  async analyzeCustomerFeedback(productId) {
    const feedbacks = await api.get('/api/feedback/list', {
      productId,
      limit: 100
    });
    
    const qualityIssues = feedbacks.filter(f => 
      f.tags.includes('质量问题') || 
      f.rating <= 2
    );
    
    const qualityIssueRate = qualityIssues.length / feedbacks.length;
    
    if (qualityIssueRate > 0.05) {
      // 质量问题超过 5%，触发深度调查
      await api.post('/api/qc/investigation/create', {
        productId,
        reason: '用户反馈质量问题率超标',
        issueRate: qualityIssueRate
      });
    }
    
    return {
      totalFeedbacks: feedbacks.length,
      qualityIssues: qualityIssues.length,
      issueRate: qualityIssueRate
    };
  }
  
  // 供应商质量评分
  async calculateSupplierScore(supplierId) {
    const inspections = await api.get('/api/qc/inspection/list', {
      supplierId,
      days: 90 // 近 90 天
    });
    
    const passRate = inspections.filter(i => i.result === 'pass').length / inspections.length;
    
    const feedbacks = await api.get('/api/feedback/supplier', {
      supplierId,
      days: 90
    });
    
    const avgRating = feedbacks.reduce((sum, f) => sum + f.rating, 0) / feedbacks.length;
    
    const score = passRate * 0.6 + (avgRating / 5) * 0.4;
    
    // 更新供应商评分
    await api.post('/api/supplier/score/update', {
      supplierId,
      qualityScore: score,
      passRate,
      avgRating
    });
    
    return score;
  }
}
```

---

### 2.7 售后协同 SOP

#### 无货源售后处理流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                      无货源售后协同流程                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  用户发起售后                                                        │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  步骤 1: 售后受理（2 小时内）                                   │    │
│  │  API: /api/afterSale/create（创建售后单）                      │    │
│  │  • 售后类型识别（退货/换货/退款）                               │    │
│  │  • 原因分类（质量/物流/描述不符）                               │    │
│  │  • 证据收集（照片/视频）                                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  步骤 2: 供应商协同（24 小时内）                                 │    │
│  │  API: /api/supplier/afterSale/notify（通知供应商）             │    │
│  │  • 质量问题→供应商承担                                        │    │
│  │  • 物流问题→物流索赔                                          │    │
│  │  • 用户原因→协商处理                                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  步骤 3: 退货处理（3-5 天）                                     │    │
│  │  API: /api/afterSale/return（退货处理）                        │    │
│  │  • 退货地址提供（供应商地址/中转仓）                            │    │
│  │  • 物流单号跟踪                                               │    │
│  │  • 收货确认                                                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  步骤 4: 退款处理（1-3 天）                                     │    │
│  │  API: /api/afterSale/refund（退款处理）                        │    │
│  │  • 退款审核                                                   │    │
│  │  • 退款执行                                                   │    │
│  │  • 供应商结算扣款                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ⏱️ 总时效要求：≤ 7 天完成                                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 售后责任划分

| 售后原因 | 责任方 | 费用承担 | 处理流程 |
|----------|--------|----------|----------|
| 质量问题 | 供应商 | 供应商承担 | 退货退款 + 供应商扣款 |
| 发错货 | 供应商 | 供应商承担 | 换货/退款 + 供应商承担运费 |
| 物流破损 | 物流/供应商 | 物流保险/供应商 | 索赔 + 补发/退款 |
| 描述不符 | 运营方 | 运营方承担 | 退货退款 + 优化描述 |
| 用户不喜欢 | 用户 | 用户承担运费 | 退货退款（扣运费） |
| 七天无理由 | 用户 | 用户承担运费 | 退货退款（扣运费） |

#### 售后 API 集成

```javascript
// 售后协同系统
class AfterSaleSystem {
  // 创建售后单
  async createAfterSale(orderId, reason, evidence) {
    const afterSale = await api.post('/api/afterSale/create', {
      orderId,
      reason,
      evidence,
      status: 'pending',
      createdAt: new Date()
    });
    
    // 获取订单对应的供应商信息
    const order = await api.get('/api/order/detail', { orderId });
    const supplier = await this.getSupplierForOrder(order);
    
    // 通知供应商
    if (['quality', 'wrong_item', 'damage'].includes(reason)) {
      await api.post('/api/supplier/afterSale/notify', {
        afterSaleId: afterSale.id,
        supplierId: supplier.id,
        reason,
        evidence,
        expectedResponse: 24 // 小时
      });
    }
    
    return afterSale;
  }
  
  // 售后责任判定
  async determineResponsibility(afterSaleId) {
    const afterSale = await api.get('/api/afterSale/detail', { afterSaleId });
    
    let responsibility = 'user'; // 默认用户责任
    
    if (afterSale.reason === 'quality') {
      // 质量问题需要供应商确认
      const supplierConfirm = await api.get('/api/supplier/afterSale/confirm', {
        afterSaleId
      });
      
      if (supplierConfirm.confirmed) {
        responsibility = 'supplier';
      } else {
        // 供应商不承认，需要第三方鉴定
        responsibility = 'pending_investigation';
      }
    } else if (afterSale.reason === 'wrong_item') {
      responsibility = 'supplier';
    } else if (afterSale.reason === 'damage') {
      // 物流破损，先找物流索赔
      const logisticsClaim = await this.fileLogisticsClaim(afterSale);
      responsibility = logisticsClaim.approved ? 'logistics' : 'supplier';
    }
    
    // 更新售后单责任方
    await api.post('/api/afterSale/responsibility/update', {
      afterSaleId,
      responsibility
    });
    
    return responsibility;
  }
  
  // 供应商结算扣款
  async deductFromSupplier(afterSaleId, amount) {
    const afterSale = await api.get('/api/afterSale/detail', { afterSaleId });
    
    if (afterSale.responsibility === 'supplier') {
      await api.post('/api/supplier/settlement/deduct', {
        supplierId: afterSale.supplierId,
        amount,
        reason: '售后扣款',
        afterSaleId
      });
    }
  }
}
```

---

## 三、API 接口汇总

### 3.1 供应链管理 API

| 类别 | 接口 | 方法 | 描述 | 调用频率 |
|------|------|------|------|----------|
| **供应商管理** | `/api/supplier/search` | GET | 供应商搜索 | 100 次/分钟 |
| | `/api/supplier/detail` | GET | 供应商详情 | 100 次/分钟 |
| | `/api/supplier/score/update` | POST | 更新供应商评分 | 50 次/分钟 |
| | `/api/supplier/stock/query` | GET | 查询供应商库存 | 200 次/分钟 |
| | `/api/supplier/stock/reserve` | POST | 库存预留 | 100 次/分钟 |
| **订单协同** | `/api/supplier/order/create` | POST | 供应商下单 | 100 次/分钟 |
| | `/api/supplier/order/tracking` | GET | 订单物流跟踪 | 200 次/分钟 |
| | `/api/supplier/afterSale/notify` | POST | 售后通知 | 50 次/分钟 |
| | `/api/supplier/settlement/deduct` | POST | 结算扣款 | 50 次/分钟 |
| **品控管理** | `/api/qc/inspection/create` | POST | 创建质检记录 | 50 次/分钟 |
| | `/api/qc/inspection/list` | GET | 质检记录查询 | 100 次/分钟 |
| | `/api/qc/alert` | POST | 质量预警 | 50 次/分钟 |
| | `/api/qc/investigation/create` | POST | 创建调查 | 20 次/天 |
| **库存管理** | `/api/inventory/sync` | POST | 库存同步 | 200 次/分钟 |
| | `/api/inventory/alert` | POST | 库存预警 | 100 次/分钟 |
| | `/api/product/stock/update` | POST | 库存更新 | 200 次/分钟 |
| | `/api/product/stock/freeze` | POST | 库存冻结 | 50 次/分钟 |

### 3.2 第三方平台 API

| 平台 | API 文档 | 核心接口 |
|------|----------|----------|
| **1688** | https://open.1688.com | 商品搜索、一键铺货、订单同步 |
| **抖音选品中心** | https://op.jinritemai.com | 选品池、商品详情、添加橱窗 |
| **快手选品中心** | https://open.kuaishou.com | 商品库、佣金设置、订单同步 |
| **淘宝联盟** | https://open.taobao.com | 商品查询、推广链接、订单跟踪 |

---

## 四、关键成功因素

### 4.1 供应商关系管理

| 策略 | 说明 | 执行频率 |
|------|------|----------|
| 定期沟通 | 与核心供应商每周沟通 | 每周 |
| 联合开发 | 与 A 级供应商共同开发新品 | 每月 |
| 培训支持 | 为供应商提供电商运营培训 | 每季度 |
| 激励政策 | 销量返点、优先结算 | 每月 |
| 淘汰机制 | 连续 3 个月评分低于 3.5 淘汰 | 每季度 |

### 4.2 风险控制

| 风险类型 | 风险描述 | 应对措施 |
|----------|----------|----------|
| 供应商断供 | 供应商突然停产/倒闭 | 保持 2-3 家备选供应商 |
| 质量波动 | 产品质量不稳定 | 批次抽检 + 定期复检 |
| 库存不同步 | 供应商库存与销售库存不一致 | 实时同步 + 安全库存 |
| 物流延误 | 供应商发货不及时 | 发货时效考核 + 违约金 |
| 售后扯皮 | 供应商不承认质量问题 | 明确协议 + 第三方检测 |

### 4.3 利润优化

```
利润优化公式：

净利润 = 售价 - 采购成本 - 平台佣金 - 运费 - 营销费用 - 售后成本

优化策略：
1. 采购成本：多家比价、批量议价、账期优化
2. 平台佣金：选择低佣金平台、提升店铺评级
3. 运费：与物流公司谈合作价、优化包装
4. 营销费用：精准投放、提升转化率
5. 售后成本：提升品控、优化描述、快速响应
```

---

## 五、附录

### 5.1 供应商合作协议模板要点

```
1. 合作范围
   - 供应商品类目
   - 供货价格体系
   - 最低起订量（MOQ）

2. 质量标准
   - 质量要求
   - 质检标准
   - 次品处理方式

3. 交货条款
   - 交货周期
   - 发货时效
   - 物流要求

4. 结算方式
   - 结算周期（月结/周结）
   - 付款方式
   - 账期长度

5. 售后责任
   - 质量问题责任划分
   - 退换货流程
   - 售后费用承担

6. 保密条款
   - 商业机密保护
   - 客户信息保密
   - 竞业限制

7. 违约责任
   - 违约情形
   - 违约金计算
   - 合同解除条件
```

### 5.2 常用工具推荐

| 工具 | 用途 | 链接 |
|------|------|------|
| 1688 商家工作台 | 供应商管理 | https://workbench.1688.com |
| 抖音选品广场 | 选品分析 | https://fxg.jinritemai.com |
| 飞瓜数据 | 电商数据分析 | https://www.feigua.cn |
| 蝉妈妈 | 直播电商数据 | https://www.chanmama.com |
| 快递 100 | 物流跟踪 | https://www.kuaidi100.com |
| 聚水潭 | ERP 系统 | https://www.jushuitan.com |

---

> **文档维护**: 网络爬虫助理 (CrawlerBot)  
> **最后更新**: 2026-03-02  
> **下次审核**: 2026-04-02  
> **关联文档**: 《电商带货 API 技术文档.md》
