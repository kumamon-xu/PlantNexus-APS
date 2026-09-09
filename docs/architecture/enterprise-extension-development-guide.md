---
doc_id: DOC-ARCH-012
title: Enterprise Extension 开发指南
status: active
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [4, 5, 9, 12, 30, 93, 95, 97, 101, 103, 107, 113, 114]
last_reviewed: 2026-09-09
---

# Enterprise Extension 开发指南

## 1. 适用范围

Enterprise Extension是在企业独立仓库中开发、由APS Runtime在服务端受控装载的Python包。企业平台仍只通过统一Headless HTTP API提交versioned canonical JSON和读取结果；Extension不是外部API、浏览器插件或第三方系统Adapter，也不得复制、vendor或修改APS Core。

TASK-P8-14提供项目模板、两份synthetic示例、确定性打包和conformance工具。TASK-P8-15现将这些输入与exact Runtime artifact、供应链证据和文档组装为Developer Kit `1.0.0`工程候选。它证明独立项目可针对固定组合构建、测试和装载，但不认证真实业务规则、外部签名或Production使用资格。

## 2. 固定开发组合

当前工具集只接受以下精确值：

| 维度 | 值 | 规则 |
|---|---|---|
| Python | `>=3.12,<3.13` | clean环境必须满足 |
| APS Extension SDK | `1.0.0` | wheel必须以精确SHA-256锁定 |
| APS Runtime | `0.1.0` | 只用于conformance装载，不是Production承诺 |
| Developer Kit | `1.0.0` | 仅接受当前compatibility matrix中的exact工程组合 |
| Extension Tooling / Template | `1.0.0` / `1.0.0` | 随Kit精确锁定；不得从`latest`推断 |
| Extension artifact | 企业独立SemVer | 已发布bytes不得覆盖 |

Core或Runtime后续升级不会自动修改企业项目。企业只有在取得新组合的兼容测试结果后，才可显式更新锁定值；旧项目可继续维护其已验证组合。

仓库中的P8-14原始模板和示例仍逐字锁定`0.0.0-not-published`，只用于历史重放。Kit组装器在临时副本中写入`1.0.0`，不修改源项目；企业新项目应从解包后的`templates/enterprise-extension`创建。

## 3. 创建独立项目

从Developer Kit解包目录运行（下面的SDK wheel文件名和Core inventory均由Kit lock给出）：

```powershell
python tools/aps_extension_conformance.py `
  --root . `
  --sdk-wheel artifacts/sdk/aps_extension_sdk-1.0.0-py3-none-any.whl `
  --core-source-inventory metadata/core-source-hashes.json `
  --runtime-version 0.1.0 `
  --developer-kit-version 1.0.0 `
  scaffold `
  --template templates/enterprise-extension `
  --output D:/enterprise/acme-capacity-extension `
  --extension-id com.acme.aps.capacity `
  --distribution-name acme-aps-capacity-extension `
  --package-name acme_aps_capacity_extension `
  --owner "Acme Planning Engineering" `
  --repository-url https://git.example.com/acme/aps-capacity-extension `
  --license-expression LicenseRef-Acme-Proprietary `
  --source-commit 0123456789abcdef0123456789abcdef01234567
```

命令只创建指定本地目录，不初始化Git、不创建远程仓库。`extension-project.v1.json`中的owner、HTTPS repository URL、license和40字符source commit必须由企业明确提供；模板token、`unknown`、浮动版本或含凭据URL都会被拒绝。

生成项目的主要内容为：

```text
extension-project.v1.json        项目身份与精确版本锁
requirements.lock               SDK wheel精确hash
extension/
  manifest.v1.json              Extension和贡献声明
  configuration-contract.v1.json
  configuration.v1.json
src/<enterprise_package>/        仅依赖SDK的实现
tests/                           可在独立clean环境执行的测试
conformance/fixture.v1.json      synthetic正反验证输入
```

企业应把项目移入自己控制的独立仓库，并按自身策略管理访问、签名、审查和发布。APS模板不推定企业源码许可证。

## 4. 实现规则

企业源码只可导入`aps_extension_sdk`公开面和允许的确定性Python标准库。禁止导入`app`、`backend`、`aps_core`、ORM、API、Worker、Solver/Validator内部实现或其他第三方运行依赖；也禁止文件、网络、环境变量、时钟、随机数、进程和动态代码执行。配置和运行事实必须由Runtime通过冻结SDK value传入。

六类扩展点遵循SDK合同：

- Constraint及影响可行性的Planning Rule必须声明同artifact的Validation Rule，并在manifest中双向配对；Solver/Planning实现和Validation实现必须位于不同模块。
- Validation Rule必须从独立输入重算，不能导入或调用Constraint实现，也不能信任Solver状态。
- Objective只能输出Core三个目标之后的`ENTERPRISE_TIE_BREAK`确定性整数项，不得改写Core目标层级。
- Replan Policy只能返回请求与否，且必须原样保留execution fact、HARD lock、freeze window、state和publication authority绑定。
- Plugin Registry必须与SDK和Runtime的确定性resolution逐值一致。
- 任一输出或校验失败都应拒绝整个调用，不得形成部分candidate或成功结论。

配置Schema、配置、manifest、source commit和dependency lock都参与artifact身份。任何业务语义或配置变更都应产生新的不可变artifact版本和digest。

## 5. 本地检查与双项目验证

检查单个项目：

```powershell
python tools/aps_extension_conformance.py `
  --root . --sdk-wheel artifacts/sdk/aps_extension_sdk-1.0.0-py3-none-any.whl `
  --core-source-inventory metadata/core-source-hashes.json `
  --runtime-version 0.1.0 --developer-kit-version 1.0.0 `
  check `
  --project D:/enterprise/acme-capacity-extension `
  --output build/enterprise-extension `
  --report build/enterprise-extension/acme-report.json
```

检查一个将共同装载的精确集合：

```powershell
python tools/aps_extension_conformance.py `
  --root . --sdk-wheel artifacts/sdk/aps_extension_sdk-1.0.0-py3-none-any.whl `
  --core-source-inventory metadata/core-source-hashes.json `
  --runtime-version 0.1.0 --developer-kit-version 1.0.0 `
  check-set `
  --project examples/enterprise-extensions/alpha-resource-tag `
  --project examples/enterprise-extensions/beta-priority-policy `
  --output build/enterprise-extension `
  --report build/enterprise-extension/example-set-report.json
```

默认检查会执行strict项目/manifest/config解析、source/import/Core-copy扫描、依赖与license校验、两次确定性wheel和项目归档构建、无索引clean venv安装、独立项目测试、Runtime受控装载、六类SPI双次回放、独立Validation负例和Registry一致性。`--skip-clean-install`只供有界诊断使用，不能作为发布或Gate证据。

报告只包含稳定身份、digest、计数、检查结果和脱敏错误，不应包含业务payload、配置值、凭据、绝对路径或堆栈。非零退出码表示artifact集合不得交付。

## 6. 示例和常见拒绝

`examples/enterprise-extensions/alpha-resource-tag`演示通用resource-tag Constraint与独立Validation Rule；`beta-priority-policy`演示Planning Rule、integer tie-break Objective、Replan Policy和Plugin Registry。两者是互不共享源码的synthetic参考，不是行业默认或真实客户规则。

工具会稳定拒绝非法manifest、不兼容SDK/Runtime、重复Extension或contribution、缺失Validator配对、Core/internal import、浮动SDK lock、非确定性/I/O源码、构建漂移、clean测试失败和Runtime set冲突。为通过工具而对白名单加入客户特例、复制Core文件或关闭Validation均不允许。

## 7. 调试、发布与升级

调试顺序是先运行项目自己的SDK-only单元测试，再执行`check`，最后用`check-set`验证实际共同部署集合。失败时依据稳定错误code修复源项目或manifest，保留失败报告；不要绕过Runtime loader、手改生成digest或从HTTP请求选择代码。

交付时应保存项目source commit、Extension wheel digest、project archive digest、manifest/config/lock digest和conformance报告。Developer Kit `1.0.0`已共同锁定exact Runtime、SDK、模板、工具、示例、文档和供应链证据，但仍是未签名工程候选；企业artifact和Production promotion需要各自批准。

升级必须创建企业自己的受控变更/版本并在新Kit候选上重跑项目与完整Extension set；APS仓库如何执行Task不改变企业治理。破坏性SDK变更要求新major；Runtime/Core变更即使不改变SDK，也必须通过兼容回放。回退应重新部署上一组已验证且内容寻址的Runtime/Extension/config组合，不覆盖旧artifact，也不在请求中临时禁用校验。P8-14占位只能作为synthetic/unpublished replay，不应称为上一正式Kit。

## 8. 安全与Production边界

Extension是`trusted_in_process=true`的部署代码，不是安全沙箱。静态扫描和timeout不能隔离恶意代码；企业仍负责代码审查、仓库权限、签名/attestation、密钥、漏洞响应、支持窗口和业务正确性。真实数据、容量、SLA、IdP/RBAC、UAT、行业规则及Production批准均不由模板或synthetic conformance结果证明。

稳定SPI与manifest语义以[APS Extension SDK与Developer Kit合同](../contracts/extension-sdk-and-developer-kit.md)为准；Runtime装载与版本关系以[Extension SDK、Runtime与Developer Kit架构](extension-sdk-runtime-and-developer-kit.md)为准。
