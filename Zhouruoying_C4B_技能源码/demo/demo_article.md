---
title: 我把排版这件小事做成了一个技能
author: Zhouruoying
date: 2026-10-05
abstract: 一次把 Markdown 变成公众号可粘贴 HTML 的改造记录。
---

# 为什么重复劳动该被工具吃掉

每次写完 Markdown 还要手动调字号、加目录、修半角标点，AI时代 的写作者不该把时间花在这上面。

## 三张图，三种格式

![JPEG 封面](demo_photo.jpg)

![GIF 动图](demo_anim.gif)

![PNG 像素](demo_pixel.png)

无法识别的文件会怎样：![坏文件](weird.bin)

> [!WARNING] 微信只认 PNG/JPG/GIF
> SVG 保存后会消失，外链图片容易被防盗链拦截。

## 一张表

| 格式 | 微信支持 | 处理方式 |
| --- | --- | --- |
| PNG | 是 | 直接内联 |
| JPEG | 是 | 无 Pillow 时按原格式内联 |
| SVG | 否 | 拦截并提示导出 PNG |

```python
def work():
    return "让工具干活"
```
