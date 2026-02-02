# preferences.json 设计

用于保存用户偏好与写作约束（可由 /webnovel-init 或用户手动编辑）。

## 示例

```json
{
  "tone": "热血",
  "pacing": {
    "chapter_words": 2500,
    "cliffhanger": true
  },
  "style": {
    "dialogue_ratio": 0.35,
    "narration_ratio": 0.65
  },
  "avoid": ["过度旁白", "重复台词"],
  "focus": ["主角成长", "战斗描写"]
}
```

## 字段说明
- tone: 全局情绪基调
- pacing: 节奏偏好
- style: 叙事/对话比例
- avoid: 禁忌清单
- focus: 必须强调的方向
