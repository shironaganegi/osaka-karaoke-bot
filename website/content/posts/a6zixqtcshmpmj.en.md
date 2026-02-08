+++
title = "New AI Tool: NoteのProseMirror対応HTML変換を作った話｜アイキャッチ画像APIも発見 (English)"
date = "2026-02-08T04:50:36.257634"
tags = ["AI", "Tools"]
draft = false
description = "Introduction to New AI Tool: NoteのProseMirror対応HTML変換を作った話｜アイキャッチ画像APIも発見 (English)"
canonicalUrl = "https://zenn.dev/shironaganegi/articles/a6zixqtcshmpmj"
+++


[Technical Analysis] The ProseMirror Data Structure of Note Articles and the Challenge of HTML Conversion: An Engineer's Impact Summary

## Introduction

As many content platforms adopt their own unique data formats, the popular platform "Note" is no exception. To deliver a sophisticated editing experience, Note utilizes [ProseMirror](https://prosemirror.net/), a structured document editor framework. This article deeply explores, from an engineering perspective, the specific approaches for converting Note articles (in the ProseMirror format) into high-quality HTML usable by external systems, including the discovery of the **Eye-Catch Image API** during the process.

## Core Features and Mechanisms of Article Data Conversion

The main function is to interpret Note's internal data structure (JSON format) and map it to standard HTML tags. A particular challenge was accurately reproducing Note-specific block elements (quotes, embeds, heading levels, etc.). This required custom schema parsing.

**1. Parsing Complex ProseMirror JSON:**
ProseMirror utilizes a tree structure combining nodes and marks. We built logic to comprehensively define the custom nodes used by Note (e.g., embedded cards, paid content paywalls) and accurately convert them into corresponding HTML tags (e.g., `<div>`, `<blockquote>`).

**2. Discovery of the Eye-Catch Image API:**
While analyzing article metadata, we discovered the **Eye-Catch Image API**, for which little public information exists. This enables the easy embedding of high-resolution eye-catch images into the converted HTML, maintaining the visual integrity of the content. Since the behavior of this API is not detailed in the [official API documentation](https://help.note.com/m/m399b62615462), this implementation leveraged knowledge gained through engineering reverse-engineering.

## Analysis and Challenges from an Engineering Perspective

The benefit of adopting ProseMirror lies in its ability to generate highly structured and reliable documents, but this presents a significant hurdle when extracting and converting data externally. Compared to standard Markdown conversion, ProseMirror's JSON is highly granular and extremely sensitive to changes in Note-specific custom node specifications.

### Utility in the Japanese Engineering Ecosystem

In the Japanese engineering ecosystem, the need for content migration and backup is increasing, yet official APIs are often nonexistent or highly restricted. This implementation offers extremely high utility for side projects requiring clean HTML or for integration with data analysis platforms. Specifically for backend engineers who need to save rich text content directly into an external database and keep it in a reusable format, this custom parser is key to significantly saving time and effort. The critical design requirement was the accurate processing of Note-specific complex nesting structures, which are difficult to handle with existing general-purpose JSON parsers.



### 👇 Recommended Services for Engineers 👇
[**🌐 Get your own domain with "Onamae.com". TechTrend Watch uses them too!**](https://www.onamae.com/)



## Installation and Usage

For the specific implementation details, please refer to the original article (Creating an HTML Converter for Note's ProseMirror | Discovery of the Eye-Catch Image API). The core conversion logic is written in TypeScript and runs in a Node.js environment. The basic usage involves fetching the Note article JSON and then passing it to the custom parser.

```javascript
// Sample Code (Conceptual)
import { ProseMirrorToHtmlConverter } from './converter';
const noteData = fetchNoteJson(articleId); // Fetch JSON using article ID
const htmlOutput = new ProseMirrorToHtmlConverter(noteData).toHtml();
console.log(htmlOutput);
```
Utilizing the Eye-Catch API is also simple; you can retrieve the image URL directly by passing the article ID. However, adherence to the Terms of Service and responsible API usage is essential.

## Advantages (Pros) and Challenges (Cons)

| Item | Advantages (Pros) | Challenges (Cons) |
|---|---|---|
| **Structural Fidelity** | High-precision reproduction of detailed Note editor structures (lists, quotes, etc.). | Potential maintenance required if Note's ProseMirror schema changes. |
| **API Discovery** | Efficient retrieval of eye-catch images, improving the quality of external integration. | Since it is not an official API, there is a risk of access being restricted in the future. |
| **Extensibility** | Design allows for easy addition of custom node renderers as needed. | Initial setup and schema comprehension require a certain learning curve. |

## Conclusion and Future Outlook

The endeavor to generate HTML from Note's ProseMirror data was more than a mere data conversion; it was a challenge that demanded a deep understanding of content structure and representation. This approach enhances content portability and provides engineers with a powerful tool for ensuring data freedom. Moving forward, the importance of platform-agnostic content management will only increase. We hope this research proves helpful to the many engineers tackling similar challenges.


---

> This article was originally published on [Zenn](https://zenn.dev/shironaganegi/articles/a6zixqtcshmpmj) (Japanese).
