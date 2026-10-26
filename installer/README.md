# 安装包构建说明

安装包使用 [Inno Setup 6](https://jrsoftware.org/isinfo.php) 编译，脚本为 `MultiSpeaker.iss`。

## 依赖

1. 先执行仓库根目录的 `build.ps1`，生成 `dist\MultiSpeaker\`（PyInstaller onedir 输出）。
2. 安装 Inno Setup 6（默认安装到 `C:\Program Files (x86)\Inno Setup 6`）。
3. 准备简体中文语言文件 `ChineseSimplified.isl`，放在本目录下：
   - 来源：社区维护的 Inno Setup 简体中文翻译
     <https://github.com/kira-96/Inno-Setup-Chinese-Simplified-Translation>
   - 该文件不随仓库分发，请自行下载后放入 `installer/`。

## 编译

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" .\installer\MultiSpeaker.iss
```

输出：`dist\MultiSpeaker-Setup-<版本>.exe`。

## 说明

- 安装模式为 **管理员**（`PrivilegesRequired=admin`），默认安装到 `C:\Program Files\MultiSpeaker`
- 安装包会创建开始菜单项、桌面快捷方式（可选）与卸载项
- 卸载时同时清理开机启动项（HKCU Run）与用户设置（HKCU\Software\MultiSpeaker）
- 安装包**不包含** VB-CABLE 虚拟声卡驱动；系统音频功能需要用户自行安装 VB-CABLE
