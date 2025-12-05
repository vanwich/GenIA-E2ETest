<p align="center">
  <img src="geniaLogo.jpg" alt="Logo do Projeto" width="150"/>
</p>

# GenIA-E2ETest：基于生成式 AI 的端到端测试自动化方法

本仓库包含随论文发布的所有材料：

**GenIA-E2ETest: A Generative AI-Based Approach for End-to-End Test Automation**，已被 **第 39 届巴西软件工程研讨会（SBES 2025）** 收录。

## 🔗 论文链接

论文完整版：
📄 [./GenIA-E2ETest.pdf](./GenIA-E2ETest.pdf)

作者：
- Elvis Júnior（巴西弗鲁米嫩塞联邦大学）
- Alan Valejo（巴西圣卡洛斯联邦大学）
- Jorge Valverde-Rebaza（墨西哥蒙特雷理工学院）
- Vânia de Oliveira Neves（巴西弗鲁米嫩塞联邦大学）

---

## 🧪 工件概览

**GenIA-E2ETest** 是一个开源方案，利用 **大语言模型（LLMs）** 将自然语言描述自动转换为 **端到端（E2E）测试脚本**，显著减少测试工程师与研究人员在用例规范和自动化上的人工成本。

该方案采用**分层提示策略**，并整合三个关键组件：
- 使用 **LLM API** 解析自然语言测试场景；
- 通过 **Crawl4AI** 自动提取并优化界面元素；
- 生成可用 **SeleniumLibrary** 执行的 **Robot Framework** 脚本。

本仓库提供复现方法、执行自动化流程以及验证论文结果所需的全部资源。

---

## 📁 仓库结构

```
GenIA-E2ETest/
├── Experiment/                         # 实验结果、验证指标与评估表格
│   └── GenIA-E2ETest.xlsx              # 评估指标和性能数据的表格
├── Prompts/                            # 各提示阶段使用的模板
│   ├── RobotTestGeneration.txt         # 生成最终 Robot Framework 脚本的提示
│   ├── TestCaseRestructuring.txt       # 重组与澄清输入测试用例的提示
│   ├── UIElementExtraction.txt         # 指导识别界面元素的提示
│   └── UIElementRefinement.txt         # 优化和校验提取 UI 元素的提示
├── TestCaseExamples/                   # 自然语言测试用例示例
│   ├── TestCase1.feature               # 手写测试场景示例
│   └── ...
├── TestCases/                          # 生成的测试脚本与中间数据
│   ├── TestCase1/                      # 某个测试用例的输出目录
│   │   ├── E2ETest.robot               # 系统生成的最终 Robot Framework 脚本
│   │   ├── ExtractedData.json          # 使用 Crawl4AI 提取的原始 UI 元素
│   │   ├── RefinedTestCase1.json       # 用于 UI 提取的 JSON 结构化测试用例
│   │   └── RefinedExtractedData.json   # 精炼后的 UI 元素数据
│   └── ...
├── .env.example                        # OpenAI API Key 的环境变量模板
├── GenIA-E2ETest.pdf                   # 通过的 SBES 2025 论文（PDF）
├── LICENSE                             # 开源许可证
├── README.md                           # 主要文档（本文件）
├── genIAE2ETest.py                     # 协调测试生成流程的主脚本
└── requirements.txt                    # 运行所需的 Python 依赖
```

---

## 📋 运行要求

### 硬件

实验与测试执行环境：

- 操作系统：Windows 11 Home Single Language 64-bit（Build 22631）
- 处理器：Intel(R) Core(TM) i7-1165G7 @ 2.80GHz（8 核）
- 内存：12 GB
- 磁盘空间：至少 1 GB 可用空间

> ℹ️ 说明：虽然评估在上述配置下完成，但项目对硬件要求不高。对于小型到中型 Web 应用，即便是双核 CPU、8 GB 内存的机器也能运行。

### 软件

项目中使用的软件环境：

- Python 3.12.3
- Robot Framework 7.2.2
- Google Chrome v135（或更高版本）
- Crawl4AI v0.5.0.post8
- Git

---

## ⚙️ 安装与使用

1. **克隆仓库**：
```bash
git clone https://github.com/uffsoftwaretesting/GenIA-E2ETest.git
cd GenIA-E2ETest
```

2. **配置 OpenAI API Key**：
```bash
copy .env.example .env
# 编辑 .env 文件并填入 OpenAI API Key
```

3. **创建并激活虚拟环境**：
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
\.\venv\Scripts\Activate
```

4. **安装依赖并配置 Playwright**：
```bash
pip install -r requirements.txt
playwright install
playwright install-deps  # 可选：仅 Linux 系统需要
```

5. **编写自然语言测试场景并指定目标 Web 应用的 URL**：
```bash
cd TestCaseExamples
# 新建 .feature 文件描述测试场景
ni TestCase1.feature
notepad TestCase1.feature
```

5.1 **`TestCase1.feature` 示例内容**：
```feature
urls = ["http://automationexercise.com", "https://automationexercise.com/login"]

Test Case 1: Login User with incorrect email and password
1. Launch browser
2. Navigate to url 'http://automationexercise.com'
3. Click on 'Signup / Login' button
4. Enter incorrect email address and password
5. Click 'login' button
6. Verify error 'Your email or password is incorrect!' is visible
```

6. **运行完整流程以生成端到端测试脚本**：
```bash
python genIAE2ETest.py
```

7. **使用 Robot Framework 执行生成的测试脚本**：
```bash
robot TestCases/TestCase1/E2ETest.robot
```

---

## 📚 伦理与法律说明

- 评估中使用的数据集和 Web 应用均为**公开可用**或**人工合成**。
- 未使用任何真实用户数据或敏感信息。
- 所有软件组件均以开源许可证发布。

---

## 📞 支持与联系

若有疑问或需要支持，请联系：
- Elvis Júnior
- Vânia Neves

---

## 📚 引用
[![Cite this paper](https://img.shields.io/badge/Cite%20this%20paper-SBES%202025-blue)](#citation)

如果你在研究或项目中使用 **GenIA-E2ETest**，请引用：

```bibtex

@inproceedings{junior2025genia,
  author       = {Elvis Junior and Alan Valejo and Jorge C. Valverde-Rebaza and Vânia O. Neves},
  title        = {GenIA‑E2ETest: A Generative AI‑Based Approach for End‑to‑End Test Automation},
  booktitle    = {Proceedings of the XXXIX Brazilian Symposium on Software Engineering (SBES)},
  year         = {2025},
  address      = {Recife-PE, Brazil}
}

```

**正文引用格式：**

```
Junior, E., Valejo, A., Valverde-Rebaza, J. C., & Neves, V. O. (2025). GenIA-E2ETest: A generative AI-based approach for end-to-end test automation. In: Proceedings of the XXXIX Brazilian Symposium on Software Engineering (SBES). To appear.

```

---

## 🌐 其他资源

- [GenIA-E2ETest GitHub 仓库](https://github.com/uffsoftwaretesting/GenIA-E2ETest)
