/* ============================================
   今晚吃什么 — Mock 数据与模拟器
   三套场景：正常推荐 / 部分缺失 / 安全阻断
   ============================================ */

const MockData = {

  // --- 场景1：正常推荐 ---
  normal: {
    request_summary: {
      ingredients: ["鸡蛋", "番茄", "土豆", "青菜"],
      servings: 2,
      assumed_staples: ["盐", "食用油", "生抽", "葱姜蒜"]
    },
    recommendations: [
      {
        recipe_id: "R001",
        title: "番茄炒蛋",
        image_url: "",
        match_score: 96,
        match_label: "完美匹配",
        estimated_time_min: 15,
        difficulty: "简单",
        servings: 2,
        used_ingredients: ["鸡蛋", "番茄"],
        missing_core: [],
        missing_optional: ["葱"],
        reason: "核心食材齐全，15分钟就能上桌，厨房新手也能轻松搞定",
        prep: ["番茄洗净切块", "鸡蛋打散，加少许盐搅匀", "葱切段（可选）"],
        steps: [
          "中火热锅，倒入食用油，油热后倒入蛋液",
          "用筷子快速划散，蛋液凝固后立即盛出",
          "锅中留底油，放入番茄块，中火翻炒至出汁",
          "加少许糖提鲜，翻炒均匀",
          "倒回炒好的鸡蛋，快速翻匀",
          "加盐调味，撒葱花，出锅装盘"
        ],
        heat_tips: "炒蛋要用中大火，快速凝固保持嫩滑；番茄要炒出红油才香",
        substitutions: [],
        safety_notes: ["鸡蛋务必充分加热至凝固，避免沙门氏菌风险"]
      },
      {
        recipe_id: "R002",
        title: "青菜鸡蛋汤",
        image_url: "",
        match_score: 88,
        match_label: "推荐",
        estimated_time_min: 10,
        difficulty: "简单",
        servings: 2,
        used_ingredients: ["鸡蛋", "青菜"],
        missing_core: [],
        missing_optional: ["豆腐"],
        reason: "核心食材齐全，10分钟快手汤，清淡健康",
        prep: ["青菜洗净切段", "鸡蛋打散", "姜切片"],
        steps: [
          "锅中加水烧开，放入姜片",
          "水开后放入青菜，煮1分钟",
          "转小火，沿锅边缓缓倒入蛋液",
          "蛋花浮起后加盐和少许胡椒粉调味",
          "滴几滴香油，出锅"
        ],
        heat_tips: "倒蛋液时火要小，这样蛋花才嫩滑不散",
        substitutions: ["没有豆腐可用粉丝代替"],
        safety_notes: []
      },
      {
        recipe_id: "R003",
        title: "番茄土豆汤",
        image_url: "",
        match_score: 85,
        match_label: "推荐",
        estimated_time_min: 20,
        difficulty: "简单",
        servings: 2,
        used_ingredients: ["番茄", "土豆"],
        missing_core: [],
        missing_optional: ["洋葱"],
        reason: "食材简单，酸甜开胃，搭配主食就是一顿好饭",
        prep: ["土豆去皮切小块", "番茄切块", "洋葱切丁（可选）"],
        steps: [
          "热锅少油，放入番茄块翻炒至软烂出汁",
          "加入土豆块，翻炒1分钟",
          "加入足量热水，大火烧开转中小火",
          "煮15分钟至土豆软烂",
          "加盐和少许胡椒粉调味",
          "撒上葱花出锅"
        ],
        heat_tips: "番茄先炒过汤底会更浓郁；土豆煮到筷子能轻松插入即可",
        substitutions: [],
        safety_notes: []
      }
    ],
    follow_up_question: null,
    trace_id: "mock-normal-001"
  },

  // --- 场景2：部分缺失 ---
  partial: {
    request_summary: {
      ingredients: ["鸡蛋"],
      servings: 2,
      assumed_staples: ["盐", "食用油", "生抽", "葱姜蒜"]
    },
    recommendations: [
      {
        recipe_id: "R004",
        title: "葱花煎蛋",
        image_url: "",
        match_score: 72,
        match_label: "可做",
        estimated_time_min: 8,
        difficulty: "简单",
        servings: 2,
        used_ingredients: ["鸡蛋"],
        missing_core: [],
        missing_optional: ["葱"],
        reason: "有鸡蛋就能做，但建议再搭配些蔬菜营养更均衡",
        prep: ["鸡蛋打散", "葱切葱花"],
        steps: [
          "鸡蛋打散，加少许盐和葱花搅匀",
          "热锅倒油，油热后倒入蛋液",
          "中小火煎至一面金黄，翻面",
          "两面金黄后出锅"
        ],
        heat_tips: "煎蛋火不要太大，中小火慢慢煎更香",
        substitutions: [],
        safety_notes: ["鸡蛋要煎熟，蛋黄凝固即可"]
      },
      {
        recipe_id: "R005",
        title: "蒸水蛋",
        image_url: "",
        match_score: 68,
        match_label: "可做",
        estimated_time_min: 15,
        difficulty: "简单",
        servings: 2,
        used_ingredients: ["鸡蛋"],
        missing_core: [],
        missing_optional: ["葱"],
        reason: "嫩滑细腻，但缺少配菜，口感比较单一",
        prep: ["鸡蛋打散", "准备温水（蛋液1.5倍量）"],
        steps: [
          "鸡蛋打散，加入1.5倍温水搅匀",
          "过筛去除泡沫",
          "碗上盖保鲜膜，扎几个小孔",
          "水开后上锅，中小火蒸10分钟",
          "取出淋生抽和香油"
        ],
        heat_tips: "蒸的时候火不能大，否则会有蜂窝",
        substitutions: [],
        safety_notes: ["鸡蛋要蒸到完全凝固"]
      }
    ],
    follow_up_question: "你目前只有鸡蛋，建议再买些番茄或青菜，可以做出更丰富的菜式。需要我帮你想想还能买什么吗？",
    trace_id: "mock-partial-001"
  },

  // --- 场景3：安全阻断 ---
  blocked: {
    request_summary: {
      ingredients: ["鸡胸肉", "花生", "黄瓜", "胡萝卜"],
      servings: 2,
      assumed_staples: ["盐", "食用油", "生抽", "葱姜蒜"]
    },
    recommendations: [
      {
        recipe_id: "R006",
        title: "黄瓜炒鸡片",
        image_url: "",
        match_score: 78,
        match_label: "已调整",
        estimated_time_min: 15,
        difficulty: "简单",
        servings: 2,
        used_ingredients: ["鸡胸肉", "黄瓜", "胡萝卜"],
        missing_core: [],
        missing_optional: [],
        reason: "已根据你的花生过敏信息，将宫保鸡丁中的花生移除，改用黄瓜炒鸡片",
        prep: ["鸡胸肉切薄片，加料酒淀粉腌制", "黄瓜胡萝卜切片"],
        steps: [
          "鸡胸肉切片，加料酒、淀粉、少许盐腌制10分钟",
          "热锅凉油，下鸡肉滑炒至变色盛出",
          "锅中底油炒胡萝卜片1分钟",
          "加入黄瓜片快速翻炒",
          "倒回鸡肉，加盐和生抽调味",
          "翻炒均匀出锅"
        ],
        heat_tips: "鸡肉滑炒时油温不要太高，变色立即盛出保持嫩滑",
        substitutions: ["原菜谱中的花生已移除"],
        safety_notes: [
          "⚠️ 已拦截原推荐「宫保鸡丁」，因其含花生，与你的过敏原冲突",
          "鸡肉务必炒至完全变白熟透",
          "砧板和刀具使用后请彻底清洗，避免交叉污染"
        ]
      }
    ],
    blocked_recipes: [
      {
        recipe_id: "R007",
        title: "宫保鸡丁",
        block_reason: "含过敏原：花生。已自动排除该推荐。"
      }
    ],
    follow_up_question: null,
    trace_id: "mock-blocked-001"
  }
};

/* ============================================
   模拟器 — 模拟后端请求和进度推送
   ============================================ */

const STAGES = [
  { id: 'normalizing', icon: '🥚🔪', text: '正在整理食材' },
  { id: 'retrieving',  icon: '📖🔍', text: '正在翻找菜谱' },
  { id: 'matching',    icon: '🧪✨', text: '正在匹配搭配' },
  { id: 'generating',  icon: '🍳🔥', text: '正在烹饪做法' },
  { id: 'reviewing',   icon: '🔒✅', text: '正在安全检查' }
];

/**
 * 模拟推荐请求
 * @param {string} inputText 用户输入
 * @param {object} constraints 约束条件
 * @param {function} onStage 阶段回调 (stageIndex, stage)
 * @param {function} onProgress 进度回调 (percent 0-100)
 * @returns {Promise<object>} 响应数据
 */
function mockRecommend(inputText, constraints, onStage, onProgress) {
  return new Promise((resolve) => {

    // 根据输入判断返回哪个场景
    let scenario;
    const text = inputText.toLowerCase();
    if (text.includes('花生') || text.includes('过敏')) {
      scenario = 'blocked';
    } else if (text.split(/[,，、\s]+/).filter(s => s.trim()).length <= 2) {
      scenario = 'partial';
    } else {
      scenario = 'normal';
    }

    const data = JSON.parse(JSON.stringify(MockData[scenario]));

    // 模拟阶段推进
    const totalStages = STAGES.length;
    const stageDuration = 1400 + Math.random() * 600; // 每阶段1.4~2秒

    let currentStage = 0;

    function advanceStage() {
      if (currentStage >= totalStages) {
        // 完成
        onProgress(100);
        setTimeout(() => resolve(data), 300);
        return;
      }

      onStage(currentStage, STAGES[currentStage]);
      onProgress(Math.round((currentStage / totalStages) * 100));

      currentStage++;
      setTimeout(advanceStage, stageDuration);
    }

    // 稍作延迟再开始（模拟网络请求发出）
    setTimeout(advanceStage, 400);
  });
}
