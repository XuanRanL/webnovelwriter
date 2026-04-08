---
name: webnovel-write
description: Writes webnovel chapters (default 2200-3500 words). Use when the user asks to write a chapter or runs /webnovel-write. Runs context, drafting, review, polish, and data extraction.
allowed-tools: Read Write Edit Grep Bash Task
---

# Chapter Writing (Structured Workflow)

## 鐩爣

- 浠ョǔ瀹氭祦绋嬩骇鍑哄彲鍙戝竷绔犺妭锛氫紭鍏堜娇鐢?`姝ｆ枃/绗瑊NNNN}绔?{title_safe}.md`锛屾棤鏍囬鏃跺洖閫€ `姝ｆ枃/绗瑊NNNN}绔?md`銆?
- 榛樿绔犺妭瀛楁暟鐩爣锛?200-3500锛堢敤鎴锋垨澶х翰鏄庣‘瑕嗙洊鏃朵粠鍏剁害瀹氾級銆?
- 淇濊瘉瀹℃煡銆佹鼎鑹层€佹暟鎹洖鍐欏畬鏁撮棴鐜紝閬垮厤鈥滃啓瀹屽嵆涓笂涓嬫枃鈥濄€?
- 杈撳嚭鐩存帴鍙鍚庣画绔犺妭娑堣垂鐨勭粨鏋勫寲鏁版嵁锛歚review_metrics`銆乣summaries`銆乣chapter_meta`銆?

## 鎵ц鍘熷垯

1. 鍏堟牎楠岃緭鍏ュ畬鏁存€э紝鍐嶈繘鍏ュ啓浣滄祦绋嬶紱缂哄叧閿緭鍏ユ椂绔嬪嵆闃绘柇銆?
2. 瀹℃煡涓庢暟鎹洖鍐欐槸纭楠わ紝`--fast`/`--minimal` 鍙厑璁搁檷绾у彲閫夌幆鑺傘€?
3. 鍙傝€冭祫鏂欎弗鏍兼寜姝ラ鎸夐渶鍔犺浇锛屼笉涓€娆℃€х亴鍏ュ叏閮ㄦ枃妗ｃ€?
4. Step 2B 涓?Step 4 鑱岃矗鍒嗙锛?B 鍙仛椋庢牸杞瘧锛? 鍙仛闂淇涓庤川鎺с€?
5. 浠讳竴姝ュけ璐ヤ紭鍏堝仛鏈€灏忓洖婊氾紝涓嶉噸璺戝叏娴佺▼銆?

> 正式小说生产默认且唯一推荐使用完整流程 `/webnovel-write`。下文出现的 `--fast` / `--minimal` 仅保留给历史兼容或调试排障；如果与完整流程要求冲突，一律以完整流程为准。


## 妯″紡瀹氫箟

- `/webnovel-write`锛歋tep 0 鈫?0.5 鈫?1 鈫?2A 鈫?2B 鈫?3+3.5(骞惰) 鈫?4 鈫?5 鈫?6 鈫?7
- `/webnovel-write --fast`锛歋tep 0 鈫?0.5 鈫?1 鈫?2A 鈫?3+3.5(骞惰) 鈫?4 鈫?5 鈫?6 鈫?7锛堣烦杩?2B锛?
- `/webnovel-write --minimal`锛歋tep 0 鈫?0.5 鈫?1 鈫?2A 鈫?3锛堜粎3涓熀纭€瀹℃煡锛岃烦杩?.5锛夆啋 4 鈫?5 鈫?6 鈫?7

鏈€灏忎骇鐗╋紙鎵€鏈夋ā寮忥級锛?
- `姝ｆ枃/绗瑊NNNN}绔?{title_safe}.md` 鎴?`姝ｆ枃/绗瑊NNNN}绔?md`
- `index.db.review_metrics` 鏂扮邯褰曪紙鍚?`overall_score`锛?
- `.webnovel/summaries/ch{NNNN}.md`
- `.webnovel/state.json` 鐨勮繘搴︿笌 `chapter_meta` 鏇存柊

### 娴佺▼纭害鏉燂紙绂佹浜嬮」锛?

- **绂佹骞舵**锛氫笉寰楀皢涓や釜 Step 鍚堝苟涓轰竴涓姩浣滄墽琛岋紙濡傚悓鏃跺仛 2A 鍜?3锛夈€?
- **绂佹璺虫**锛氫笉寰楄烦杩囨湭琚ā寮忓畾涔夋爣璁颁负鍙烦杩囩殑 Step銆傚嵆浣挎壒閲忓啓澶氱珷銆佽刀杩涘害銆佷笂涓嬫枃绱у紶锛屼篃蹇呴』姣忕珷瀹屾暣鎵ц鎵€鏈?Step銆備换浣?鍏堝啓瀹屽啀琛ュ"銆?璺宠繃 Context Agent 鐩存帴璧疯崏"銆?鍙窇澶栭儴瀹℃煡涓嶈窇鍐呴儴瀹℃煡"鐨勮涓哄潎瑙嗕负杩濊銆?
- **绂佹璧惰繘搴﹂檷绾?*锛氭壒閲忓啓浣滃绔犳椂锛屾瘡涓€绔犻兘蹇呴』鐙珛璧板畬瀹屾暣娴佺▼锛圫tep 0鈫?鈫?A鈫?B鈫?鈫?.5鈫?鈫?鈫?鈫?锛夈€備笉寰楀洜涓?鍚庨潰杩樻湁寰堝绔?鑰岀畝鍖栦换浣曚竴绔犵殑娴佺▼銆傝川閲忎紭鍏堜簬閫熷害锛岃繖鏄笉鍙崗鍟嗙殑纭鍒欍€?
- **绂佹鐪佺暐瀹℃煡鎶ュ憡**锛歋tep 3 瀹屾垚鍚庡繀椤荤敓鎴愬鏌ユ姤鍛婃枃浠讹紙`瀹℃煡鎶ュ憡/绗瑊NNNN}绔犲鏌ユ姤鍛?md`锛夛紝鍖呭惈鎵€鏈夊鏌ュ櫒鐨勭粨鏋滄眹鎬汇€備笉寰楀彧鍦ㄥ唴瀛樹腑姹囨€诲垎鏁拌€屼笉鍐欐枃浠躲€?
- **绂佹涓存椂鏀瑰悕**锛氫笉寰楀皢 Step 鐨勮緭鍑轰骇鐗╂敼鍐欎负闈炴爣鍑嗘枃浠跺悕鎴栨牸寮忋€?
- **绂佹鑷垱妯″紡**锛歚--fast` / `--minimal` 鍙厑璁告寜涓婃柟瀹氫箟瑁佸壀姝ラ锛屼笉鍏佽鑷垱娣峰悎妯″紡銆?鍗婃"鎴?绠€鍖栫増"銆?
- **绂佹鑷鏇夸唬**锛歋tep 3 瀹℃煡蹇呴』鐢?Task 瀛愪唬鐞嗘墽琛岋紝涓绘祦绋嬩笉寰楀唴鑱斾吉閫犲鏌ョ粨璁恒€?
- **绂佹涓昏浼板垎**锛歚overall_score` 蹇呴』鏉ヨ嚜瀹℃煡瀛愪唬鐞嗙殑鑱氬悎缁撴灉锛屼笉寰楀洜涓?瀛愪唬鐞嗚繕娌¤繑鍥?鑰岃嚜琛屼及绠楀垎鏁般€?
- **绂佹婧愮爜鎺㈡祴**锛氳剼鏈皟鐢ㄦ柟寮忎互鏈枃妗ｄ笌 data-agent 鏂囨。涓殑鍛戒护绀轰緥涓哄噯锛屽懡浠ゅけ璐ユ椂鏌ユ棩蹇楀畾浣嶉棶棰橈紝涓嶅幓缈绘簮鐮佸涔犺皟鐢ㄦ柟寮忋€?

### 绔犺妭闂撮椄闂紙Chapter Gate锛?

鍦ㄥ紑濮嬩笅涓€绔犵殑浠讳綍姝ラ锛堝寘鎷?Step 0锛変箣鍓嶏紝蹇呴』楠岃瘉褰撳墠绔犵殑浠ヤ笅鏉′欢鍏ㄩ儴婊¤冻锛?

1. Step 3 鐨勫唴閮?checker 鍏ㄩ儴杩斿洖骞舵眹鎬诲嚭 overall_score锛堟爣鍑?`--fast` 涓?10 涓紝`--minimal` 涓?3 涓牳蹇?checker锛?
2. Step 3.5 鐨?9 涓閮ㄦā鍨嬪鏌ュ畬鎴愶紙鏍稿績3妯″瀷 kimi/glm/qwen-plus 蹇呴』鎴愬姛锛岃ˉ鍏?妯″瀷澶辫触涓嶉樆濉烇級锛屾瘡妯″瀷瀹℃煡 10 涓淮搴︼紙`--minimal` 妯″紡璺宠繃姝ゆ潯浠讹級
3. 鎵€鏈?critical 闂宸蹭慨澶嶏紝high 闂宸蹭慨澶嶆垨鏈?deviation 璁板綍
4. 瀹℃煡鎶ュ憡 .md 鏂囦欢宸茬敓鎴愶紙鏍囧噯/`--fast` 妯″紡鍚唴閮?0缁村害鍒嗘暟+澶栭儴9妯″瀷脳10缁村害璇勫垎鐭╅樀锛沗--minimal` 妯″紡浠呭惈鍐呴儴3缁村害鍒嗘暟锛?
5. Step 4 鐨?`anti_ai_force_check=pass`
6. Step 5 Data Agent 宸插畬鎴?
7. Step 6 Audit Gate 鍐宠 鈭?{approve, approve_with_warnings}锛坆lock 绂佹杩涘叆 Step 7锛?
8. Step 7 Git 宸叉彁浜?

楠岃瘉鏂瑰紡锛氬湪寮€濮嬩笅涓€绔?Step 0 涔嬪墠锛屾墽琛屼互涓嬫鏌ワ細
```bash
ls "${PROJECT_ROOT}/姝ｆ枃/绗?{chapter_padded}绔?*.md >/dev/null 2>&1 && \
test -f "${PROJECT_ROOT}/瀹℃煡鎶ュ憡/绗?{chapter_padded}绔犲鏌ユ姤鍛?md" && \
test -f "${PROJECT_ROOT}/.webnovel/summaries/ch${chapter_padded}.md" && \
test -f "${PROJECT_ROOT}/.webnovel/audit_reports/ch${chapter_padded}.json" && \
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" audit check-decision --chapter ${chapter_num} --require approve,approve_with_warnings && \
git log --oneline -1 | grep "绗?{chapter_num}绔?
```
浠讳竴鏉′欢涓嶆弧瓒筹紝绂佹寮€濮嬩笅涓€绔犮€傛柊澧為椄闂ㄦ潯浠讹細
- `audit_reports/ch{NNNN}.json` 瀛樺湪锛圫tep 6 浜х墿锛?
- audit decision 涓嶇瓑浜?`block`锛堝璁℃湭閫氳繃绂佹杩涘叆涓嬩竴绔狅級

**绂佹鍦?checker 杩愯鏈熼棿寮€濮嬩笅涓€绔犵殑璧疯崏銆?* 绛夊緟鏄祦绋嬬殑涓€閮ㄥ垎锛屼笉鏄氮璐规椂闂淬€?

## 寮曠敤鍔犺浇绛夌骇锛坰trict, lazy锛?

- L0锛氭湭杩涘叆瀵瑰簲姝ラ鍓嶏紝涓嶅姞杞戒换浣曞弬鑰冩枃浠躲€?
- L1锛氭瘡姝ヤ粎鍔犺浇璇ユ鈥滃繀璇烩€濇枃浠躲€?
- L2锛氫粎鍦ㄨЕ鍙戞潯浠舵弧瓒虫椂鍔犺浇鈥滄潯浠跺繀璇?鍙€夆€濇枃浠躲€?

璺緞绾﹀畾锛?
- `references/...` 鐩稿褰撳墠 skill 鐩綍銆?
- `../../references/...` 鎸囧悜鍏ㄥ眬鍏变韩鍙傝€冦€?

## References锛堥€愭枃浠跺紩鐢ㄦ竻鍗曪級

### 鏍圭洰褰?

- `references/step-3-review-gate.md`
  - 鐢ㄩ€旓細Step 3 瀹℃煡璋冪敤妯℃澘銆佹眹鎬绘牸寮忋€佽惤搴?JSON 瑙勮寖銆?
  - 瑙﹀彂锛歋tep 3 蹇呰銆?
- `references/step-3.5-external-review.md`
  - 鐢ㄩ€旓細Step 3.5 澶栭儴妯″瀷瀹℃煡瀹屾暣瑙勮寖锛?妯″瀷鏋舵瀯/渚涘簲鍟唂allback閾?Prompt妯℃澘/杈撳嚭JSON Schema/璺敱楠岃瘉/瀹℃煡鎶ュ憡妯℃澘锛夈€?
  - 瑙﹀彂锛歋tep 3.5 蹇呰銆?
- `references/step-5-debt-switch.md`
  - 鐢ㄩ€旓細Step 5 鍊哄姟鍒╂伅寮€鍏宠鍒欙紙榛樿鍏抽棴锛夈€?
  - 瑙﹀彂锛歋tep 5 蹇呰銆?
- `references/step-6-audit-gate.md`
  - 鐢ㄩ€旓細Step 6 瀹¤闂搁棬璋冪敤妯℃澘銆佹墽琛屾椂搴忋€佸喅璁€昏緫銆佷骇鐗╃害瀹氥€佸け璐ユ仮澶嶈矾寰勩€?
  - 瑙﹀彂锛歋tep 6 蹇呰锛堜富娴佺▼ + audit-agent 鍏卞悓娑堣垂锛夈€?
- `references/step-6-audit-matrix.md`
  - 鐢ㄩ€旓細Step 6 涓冨眰瀹¤鐭╅樀锛圓 杩囩▼鐪熷疄鎬?/ B 璺ㄤ骇鐗╀竴鑷存€?/ C 璇昏€呬綋楠?/ D 浣滃搧杩炵画鎬?/ E 鍒涗綔宸ヨ壓 / F 棰樻潗鍏戠幇 / G 璺ㄧ珷瓒嬪娍锛夛紝绾?70 涓鏌ラ」銆?
  - 瑙﹀彂锛歋tep 6 蹇呰锛坅udit-agent 鎵ц鏃跺姞杞斤級銆?
- `../../references/shared/core-constraints.md`
  - 鐢ㄩ€旓細Step 2A 鍐欎綔纭害鏉燂紙澶х翰鍗虫硶寰?/ 璁惧畾鍗崇墿鐞?/ 鍙戞槑闇€璇嗗埆锛夈€?
  - 瑙﹀彂锛歋tep 2A 蹇呰銆?
- `references/polish-guide.md`
  - 鐢ㄩ€旓細Step 4 闂淇銆丄nti-AI 涓?No-Poison 瑙勫垯銆?
  - 瑙﹀彂锛歋tep 4 蹇呰銆?
- `references/writing/typesetting.md`
  - 鐢ㄩ€旓細Step 4 绉诲姩绔槄璇绘帓鐗堜笌鍙戝竷鍓嶉€熸煡銆?
  - 瑙﹀彂锛歋tep 4 蹇呰銆?
- `references/style-adapter.md`
  - 鐢ㄩ€旓細Step 2B 椋庢牸杞瘧瑙勫垯锛屼笉鏀瑰墽鎯呬簨瀹炪€?
  - 瑙﹀彂锛歋tep 2B 鎵ц鏃跺繀璇伙紙`--fast`/`--minimal` 璺宠繃锛夈€?
- `references/style-variants.md`
  - 鐢ㄩ€旓細Step 1锛堝唴缃?Contract锛夊紑澶?閽╁瓙/鑺傚鍙樹綋涓庨噸澶嶉闄╂帶鍒躲€?
  - 瑙﹀彂锛歋tep 1 褰撻渶瑕佸仛宸紓鍖栬璁℃椂鍔犺浇銆?
- `../../references/reading-power-taxonomy.md`
  - 鐢ㄩ€旓細Step 1锛堝唴缃?Contract锛夐挬瀛愩€佺埥鐐广€佸井鍏戠幇 taxonomy銆?
  - 瑙﹀彂锛歋tep 1 褰撻渶瑕佽拷璇诲姏璁捐鏃跺姞杞姐€?
- `../../references/genre-profiles.md`
  - 鐢ㄩ€旓細Step 1锛堝唴缃?Contract锛夋寜棰樻潗閰嶇疆鑺傚闃堝€间笌閽╁瓙鍋忓ソ銆?
  - 瑙﹀彂锛歋tep 1 褰?`state.project.genre` 宸茬煡鏃跺姞杞姐€?
- `references/writing/genre-hook-payoff-library.md`
  - 鐢ㄩ€旓細鐢电珵/鐩存挱鏂?鍏嬭嫃椴佺殑閽╁瓙涓庡井鍏戠幇蹇€熷簱銆?
  - 瑙﹀彂锛歋tep 1 棰樻潗鍛戒腑 `esports/livestream/cosmic-horror` 鏃跺繀璇汇€?

### writing锛堥棶棰樺畾鍚戝姞璇伙級

- `references/writing/combat-scenes.md`
  - 瑙﹀彂锛氭垬鏂楃珷鎴栧鏌ュ懡涓€滄垬鏂楀彲璇绘€?闀滃ご娣蜂贡鈥濄€?
- `references/writing/dialogue-writing.md`
  - 瑙﹀彂锛氬鏌ュ懡涓?OOC銆佸璇濊鏄庝功鍖栥€佸鐧借鲸璇嗗樊銆?
- `references/writing/emotion-psychology.md`
  - 瑙﹀彂锛氭儏缁浆鎶樼敓纭€佸姩鏈烘柇灞傘€佸叡鎯呭急銆?
- `references/writing/scene-description.md`
  - 瑙﹀彂锛氬満鏅┖娉涖€佺┖闂存柟浣嶄笉娓呫€佸垏鍦虹獊鍏€銆?
- `references/writing/desire-description.md`
  - 瑙﹀彂锛氫富瑙掔洰鏍囧急銆佹鏈涢┍鍔ㄥ姏涓嶈冻銆?
- `references/writing/classical-references.md`
  - 鐢ㄩ€旓細鍏告晠/璇楄瘝/鍙叉枡/鍘熷垱鍙ｈ瘈/浜掕仈缃戞鐨勮瀺鍏ユ妧宸с€佸瘑搴︽帶鍒躲€?鍏告晠鍗充紡绗?鎶€娉曘€侀」鐩瀹氶泦妯℃澘銆?
  - 瑙﹀彂锛歋tep 1 璁捐寮曠敤鏂规鏃?/ 瀹℃煡鍛戒腑"寮曠敤鐢熺‖/鐐/鍑哄閿欒" / Step 4 淇寮曠敤闂銆?

## 宸ュ叿绛栫暐锛堟寜闇€锛?

- `Read/Grep`锛氳鍙?`state.json`銆佸ぇ绾层€佺珷鑺傛鏂囦笌鍙傝€冩枃浠躲€?
- `Bash`锛氳繍琛?`extract_chapter_context.py`銆乣index_manager`銆乣workflow_manager`銆?
- `Task`锛氳皟鐢?`context-agent`銆佸鏌?subagent銆乣data-agent` 骞惰鎵ц銆?

## 浜や簰娴佺▼

### Step 0锛氶妫€涓庝笂涓嬫枃鏈€灏忓姞杞?

蹇呴』鍋氾細
- 瑙ｆ瀽鐪熷疄涔﹂」鐩牴锛坆ook project_root锛夛細蹇呴』鍖呭惈 `.webnovel/state.json`銆?
- 鏍￠獙鏍稿績杈撳叆锛歚澶х翰/鎬荤翰.md`銆乣${CLAUDE_PLUGIN_ROOT}/scripts/extract_chapter_context.py` 瀛樺湪銆?
- 瑙勮寖鍖栧彉閲忥細
  - `WORKSPACE_ROOT`锛欳laude Code 鎵撳紑鐨勫伐浣滃尯鏍圭洰褰曪紙鍙兘鏄功椤圭洰鐨勭埗鐩綍锛屼緥濡?`D:\wk\xiaoshuo`锛?
  - `PROJECT_ROOT`锛氱湡瀹炰功椤圭洰鏍圭洰褰曪紙蹇呴』鍖呭惈 `.webnovel/state.json`锛屼緥濡?`D:\wk\xiaoshuo\鍑′汉璧勬湰璁篳锛?
  - `SKILL_ROOT`锛歴kill 鎵€鍦ㄧ洰褰曪紙鍥哄畾 `${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write`锛?
  - `SCRIPTS_DIR`锛氳剼鏈洰褰曪紙鍥哄畾 `${CLAUDE_PLUGIN_ROOT}/scripts`锛?
  - `chapter_num`锛氬綋鍓嶇珷鍙凤紙鏁存暟锛?
  - `chapter_padded`锛氬洓浣嶇珷鍙凤紙濡?`0007`锛?

鐜璁剧疆锛坆ash 鍛戒护鎵ц鍓嶏級锛?
```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT:?CLAUDE_PLUGIN_ROOT is required}/scripts"
export SKILL_ROOT="${CLAUDE_PLUGIN_ROOT:?CLAUDE_PLUGIN_ROOT is required}/skills/webnovel-write"

python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" preflight
export PROJECT_ROOT="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
```

**纭棬妲?*锛歚preflight` 蹇呴』鎴愬姛銆傚畠缁熶竴鏍￠獙 `CLAUDE_PLUGIN_ROOT` 娲剧敓鍑虹殑 `SKILL_ROOT` / `SCRIPTS_DIR`銆乣webnovel.py`銆乣extract_chapter_context.py` 鍜岃В鏋愬嚭鐨?`PROJECT_ROOT`銆備换涓€澶辫触閮界珛鍗抽樆鏂€?

鍏告晠寮曠敤搴撴鏌ワ紙闈為樆鏂紝浠呮彁绀猴級锛?
```bash
test -f 鈥?{PROJECT_ROOT}/璁惧畾闆?鍏告晠寮曠敤搴?md鈥?&& echo 鈥滃吀鏁呭紩鐢ㄥ簱: 宸插氨缁€?|| echo 鈥滃吀鏁呭紩鐢ㄥ簱: 鏈垱寤猴紙寤鸿鍒涘缓浠ユ彁鍗囨枃鍖栬川鎰燂紝妯℃澘瑙?references/writing/classical-references.md锛夆€?
test -f 鈥?{PROJECT_ROOT}/璁惧畾闆?鍘熷垱璇楄瘝鍙ｈ瘈.md鈥?&& echo 鈥滃師鍒涜瘲璇嶅彛璇€: 宸插氨缁€?|| echo 鈥滃師鍒涜瘲璇嶅彛璇€: 鏈垱寤猴紙鍙€夛級鈥?
```

杈撳嚭锛?
- 鈥滃凡灏辩华杈撳叆鈥濅笌鈥濈己澶辫緭鍏モ€濇竻鍗曪紱缂哄け鍒欓樆鏂苟鎻愮ず鍏堣ˉ榻愩€?
- 鍏告晠寮曠敤搴撳瓨鍦ㄧ姸鎬侊紙涓嶉樆鏂紝浠呮彁绀哄缓璁級銆?

### Step 0.5锛氬伐浣滄祦鏂偣璁板綍锛坆est-effort锛屼笉闃绘柇锛?

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-task --command webnovel-write --chapter {chapter_num} || true
# 鍦ㄦ瘡涓疄闄呮楠ゅ紑濮?缁撴潫鏃跺垎鍒皟鐢ㄤ竴娆★細
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step X" --step-name "瀹為檯姝ラ鍚? || true
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step X" --artifacts '{"ok":true}' || true
# 鍏ㄩ儴姝ラ锛堢洿鍒?Step 7锛夊畬鎴愬悗锛屽啀璋冪敤 complete-task锛?python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-task --artifacts '{"chapter_completed":true}' || true
```

瑕佹眰锛?
- `--step-id` 浠呭厑璁革細`Step 1` / `Step 2A` / `Step 2B` / `Step 3` / `Step 3.5` / `Step 4` / `Step 5` / `Step 6` / `Step 7`銆?
- 浠讳綍璁板綍澶辫触鍙璀﹀憡锛屼笉闃绘柇鍐欎綔銆?
- 姣忎釜 Step 鎵ц缁撴潫鍚庯紝鍚屾牱闇€瑕?`complete-step`锛堝け璐ヤ笉闃绘柇锛夈€?

### Search Tool 浣跨敤瑙勫垯锛堝叏娴佺▼閫傜敤锛?

**鎼滅储缁熶竴浣跨敤 Tavily 鐩磋繛 API 鑴氭湰**锛坄${SCRIPTS_DIR}/tavily_search.py`锛夛紝绂佹浣跨敤 MCP 宸ュ叿锛圵ebSearch/WebFetch锛夈€?

**涓ょ鎼滅储妯″紡**锛?
- **蹇€熸悳绱?*锛堝ぇ澶氭暟鍦烘櫙锛夛細`python -X utf8 "${SCRIPTS_DIR}/tavily_search.py" search "鏌ヨ璇? --max 5`
- **娣卞害鐮旂┒**锛堝鏉備笓涓氶鍩燂級锛歚python -X utf8 "${SCRIPTS_DIR}/tavily_search.py" research "鐮旂┒闂" --model pro`

鎼滅储瑙﹀彂瑙勫垯锛?
- **寮哄埗瑙﹀彂**锛氭秹鍙婁笓涓氶鍩燂紙鏈虹敳鎶€鏈?鍐涗簨/绉戝/娉曞緥锛夆啋 鎼滅储鏈鍜岀湡瀹炵粏鑺?
- **寮哄埗瑙﹀彂**锛氶渶瑕佺壒瀹氭渚嬫垨鍙傝€冿紙濡?鐪熷疄椹鹃┒鑸卞竷灞€""鍦颁笅閫氶亾鍦拌川缁撴瀯"锛夆啋 鎼滅储鍏蜂綋璧勬枡
- **鎺ㄨ崘瑙﹀彂**锛氱珷鑺傜被鍨嬬壒娈婏紙鎴樻枟/鎯呮劅/鎻/杩介€?璋堝垽锛夆啋 鎼滅储璇ョ被鍨嬪啓浣滄妧宸?
- **鎺ㄨ崘瑙﹀彂**锛氭柊鍗烽绔犳垨Ch1-3 鈫?鎼滅储鍚岄鏉愬紑绡囨妧宸?
- **鎺ㄨ崘瑙﹀彂**锛氬鏌ュ彂鐜?HIGH 绾?STYLE/PACING 闂 鈫?鎼滅储鏀硅繘鏂规硶
- **鎸夐渶瑙﹀彂**锛氭櫘閫氭帹杩涚珷鏃犵壒娈婂満鏅?鈫?涓嶆悳绱?

鍚?Step 鐨勫叿浣撴悳绱㈠唴瀹癸細
- Step 1锛氭悳绱㈡湰绔犲満鏅被鍨嬬殑鍐欎綔鎶€宸э紙"鏈虹敳鎴樻枟 鎻忓啓鎶€宸?"璋堝垽鍦烘櫙 寮犲姏鍐欐硶"锛?
- Step 2A锛氭悳绱笓涓氶鍩熸湳璇拰鐪熷疄缁嗚妭锛?鏈虹敳椹鹃┒鑸?鎿嶆帶鐣岄潰""鍐涗簨閫氳 鍔犲瘑鏈"锛?
- Step 2B锛氭悳绱㈤鏍煎弬鑰冿紙"纭牳绉戝够 鎶€鏈弿鍐?鑼冧緥"锛?
- Step 4锛氭悳绱㈠鏌ラ棶棰樼殑鏀硅繘鏂规硶锛?瀵硅瘽骞虫贰 鏀硅繘鎶€宸?"鑺傚鎷栨矒 濡備綍鍔犲揩"锛?

鎼滅储缁撴灉褰掓。锛氭湁浠峰€肩殑涓撲笟淇℃伅淇濆瓨鍒?`璋冪爺绗旇/` 瀵瑰簲涓婚鏂囦欢锛屼緵鍚庣画绔犺妭澶嶇敤銆?

**Search 澶辫触澶勭悊鍗忚锛堢‖瑙勫垯锛?*锛?
濡傛灉 `tavily_search.py` 鎵ц澶辫触锛圓PI key 缂哄け/鍏ㄩ儴 key 鑰楀敖/缃戠粶瓒呮椂锛夛細
1. 绔嬪嵆鍋滄褰撳墠宸ヤ綔
2. 鍛婄煡鐢ㄦ埛鎼滅储鑴氭湰鎵ц澶辫触鍙婂叿浣撻敊璇俊鎭?
3. 寤鸿鐢ㄦ埛妫€鏌?API key 閰嶇疆锛堢幆澧冨彉閲?`TAVILY_API_KEYS` / `.env` 鏂囦欢 / `~/.claude.json`锛?
4. 绛夊緟鐢ㄦ埛淇閰嶇疆鍚庡啀缁х画
5. 涓嶈璺宠繃鎼滅储姝ラ鐩存帴缁х画鈥斺€旀悳绱㈣幏鍙栫殑涓撲笟缁嗚妭鐩存帴褰卞搷璐ㄩ噺

### Step 1锛欳ontext Agent锛堝唴缃?Context Contract锛岀敓鎴愮洿鍐欐墽琛屽寘锛?

浣跨敤 Task 璋冪敤 `context-agent`锛屽弬鏁帮細
- `chapter`
- `project_root`
- `storage_path=.webnovel/`
- `state_file=.webnovel/state.json`

Context Agent 棰濆杈撳叆锛堝繀璇伙級锛?
- `璁惧畾闆?浼忕瑪杩借釜.md`锛堟墍鏈?娲昏穬"浼忕瑪绾匡紝纭繚闀跨嚎浼忕瑪涓嶈閬楀繕锛?
- `璁惧畾闆?閬撳叿涓庢妧鏈?md`锛堝甫绔犺妭鏃堕棿绾匡紝闃叉寮曠敤"杩樻病鍑虹幇鐨?閬撳叿锛?
- `璁惧畾闆?鍏告晠寮曠敤搴?md`锛堣嫢瀛樺湪锛氭鏌ユ湰绔犲ぇ绾叉槸鍚︽湁寮曠敤閿氱偣锛屾帹鑽?0-2 鏉″紩鐢ㄥ苟鏍囨敞杞戒綋涓庤瀺鍏ユ柟寮忋€傛棤閿氱偣鏃惰緭鍑?鏈珷涓嶅紩鐢?銆傝嫢涓嶅瓨鍦細璺宠繃锛?
- `璁惧畾闆?鍘熷垱璇楄瘝鍙ｈ瘈.md`锛堣嫢瀛樺湪锛氬師鍒涘彛璇€浼樺厛绾ч珮浜庡閮ㄥ吀鏁咃紝妫€鏌ユ湰绔犳槸鍚﹀懡涓娇鐢ㄨ鍒掋€傝嫢涓嶅瓨鍦細璺宠繃锛?
- `澶х翰/绗琋鍗?鑺傛媿琛?md`锛堟湰鍗峰畯瑙傝妭濂忛敋鐐癸級
- 鐩稿叧瑙掕壊鍗＄殑"璇煶瑙勫垯"娈佃惤锛堟敞鍏?beat 鐨勫璇濋鏍兼寚瀵硷級

纭姹傦細
- 鑻?`state` 鎴栧ぇ绾蹭笉鍙敤锛岀珛鍗抽樆鏂苟杩斿洖缂哄け椤广€?
- 杈撳嚭蹇呴』鍚屾椂鍖呭惈锛?
  - 8 鏉垮潡浠诲姟涔︼紙鏍稿績浠诲姟/鎵挎帴/瑙掕壊/鍦烘櫙绾︽潫/鏃堕棿绾︽潫/椋庢牸鎸囧/杩炵画鎬т笌浼忕瑪/杩借鍔涚瓥鐣ワ級锛?
  - Context Contract 鍏ㄥ瓧娈碉紙鐩爣/闃诲姏/浠ｄ环/鏈珷鍙樺寲/鏈棴鍚堥棶棰?鏍稿績鍐茬獊涓€鍙ヨ瘽/寮€澶寸被鍨?鎯呯华鑺傚/淇℃伅瀵嗗害/鏄惁杩囨浮绔?杩借鍔涜璁?鐖界偣瑙勫垝/鎯呮劅閿氱偣瑙勫垝/鏃堕棿绾︽潫锛夛紱
  - Step 2A 鍙洿鎺ユ秷璐圭殑鈥滃啓浣滄墽琛屽寘鈥濓紙绔犺妭鑺傛媿銆佷笉鍙彉浜嬪疄娓呭崟銆佺姝簨椤广€佺粓妫€娓呭崟锛夈€?
- 鍐欎綔鎵ц鍖呯殑姣忎釜 beat 蹇呴』鍖呭惈锛氬瓧鏁板垎閰嶃€佸満鏅弿杩帮紙鍦扮偣+姘涘洿锛夈€佹儏缁洸绾夸綅缃€佹劅瀹橀敋鐐癸紙鑷冲皯1涓敾闈級銆佹儏鎰熼敋鐐癸紙鎯呮劅beat锛氶敋鐐圭被鍨?姊害浣嶇疆锛夈€佸叧閿璇濇柟鍚?璇煶瑙勫垯锛堣嫢鏈夊璇濓級銆佹湰beat绂佹浜嬮」銆?
- 鍚堝悓涓庝换鍔′功鍑虹幇鍐茬獊鏃讹紝浠モ€滃ぇ绾蹭笌璁惧畾绾︽潫鏇翠弗鏍艰€呪€濅负鍑嗐€?

杈撳嚭锛?
- 鍗曚竴鈥濆垱浣滄墽琛屽寘鈥濓紙浠诲姟涔?+ Context Contract + 鐩村啓鎻愮ず璇嶏級锛屼緵 Step 2A 鐩存帴娑堣垂銆侰ontext Contract 鍐呯疆浜?Step 1锛屾棤鐙珛 Step銆?

Step 1 瀹屾垚鍚庡繀椤婚獙璇?context_snapshot 瀛樺湪锛圫tep 6 A1 瀹¤渚濊禆姝ゆ枃浠讹級锛?
```bash
test -f 鈥?{PROJECT_ROOT}/.webnovel/context_snapshots/ch${chapter_padded}.json鈥?&& echo 鈥渟napshot OK鈥?
```
鑻ヤ笉瀛樺湪锛屾墜鍔ㄨˉ璺戯細
```bash
python -X utf8 鈥?{SCRIPTS_DIR}/webnovel.py鈥?--project-root 鈥?{PROJECT_ROOT}鈥?context -- --chapter ${chapter_num}
```
琛ヨ窇鍚庝粛涓嶅瓨鍦ㄦ椂锛岄渶鎵嬪姩鍒涘缓 v1 鏍煎紡 snapshot锛坧ayload 鍚?8 鏉垮潡 + contract 12 瀛楁锛夛紝纭繚 Step 6 A1 涓嶄細鍥犵己澶辫€?fail銆?

寮€绡囬粍閲戝崗璁紙Ch1-3 涓撶敤锛屽彔鍔犲湪鏍囧噯娴佺▼涔嬩笂锛夛細
- Ch1锛氫富瑙掑湪鍓?500 瀛楀唴鍑哄満涓旂敤琛屽姩灞曠ず锛堥潪鏃佺櫧浠嬬粛锛?
- Ch1锛氭牳蹇冨啿绐佹垨涓栫晫瑙勫垯鍦ㄥ墠 1000 瀛楀唴鏆楃ず锛圫how not Tell锛?
- Ch1锛氱珷鏈挬瀛愬己搴﹀己鍒?strong
- Ch1-2锛氶噾鎵嬫寚鑷冲皯鏆楃ず瀛樺湪
- Ch1-3锛氫汉鐗╁悕瀛楁€绘暟涓嶈秴杩?5 涓?
- Ch1-3锛氳嚦灏?5 涓啿绐佺偣
- Ch1-3锛氱涓€涓満鏅繀椤诲寘鍚嚦灏?1 涓叿璞℃暟瀛楋紙灞曠ず涓栫晫瑙傞噺绾э級

### Step 2A锛氭鏂囪捣鑽?

鎵ц鍓嶅繀椤诲姞杞斤細
```bash
cat "${SKILL_ROOT}/../../references/shared/core-constraints.md"
```

纭姹傦細
- 鍙緭鍑虹函姝ｆ枃鍒扮珷鑺傛鏂囨枃浠讹紱鑻ヨ缁嗗ぇ绾插凡鏈夌珷鑺傚悕锛屼紭鍏堜娇鐢?`姝ｆ枃/绗瑊chapter_padded}绔?{title_safe}.md`锛屽惁鍒欏洖閫€涓?`姝ｆ枃/绗瑊chapter_padded}绔?md`銆?
- 榛樿鎸?2200-3500 瀛楁墽琛岋紱鑻ュぇ绾蹭负鍏抽敭鎴樻枟绔?楂樻疆绔?鍗锋湯绔犳垨鐢ㄦ埛鏄庣‘鎸囧畾锛屽垯鎸夊ぇ绾?鐢ㄦ埛浼樺厛銆?
- 绂佹鍗犱綅绗︽鏂囷紙濡?`[TODO]`銆乣[寰呰ˉ鍏匽`锛夈€?
- 淇濈暀鎵挎帴鍏崇郴锛氳嫢涓婄珷鏈夋槑纭挬瀛愶紝鏈珷蹇呴』鍥炲簲锛堝彲閮ㄥ垎鍏戠幇锛夈€?
- 鐖界偣瀵嗗害绾︽潫锛氭瘡 800 瀛楄嚦灏戝畨鎺?1 涓井鐖界偣锛堜俊鎭彮绀?灏忚儨/璁ゅ彲/閫嗚浆/鍏戠幇锛夛紱绾摵鍨珷鍏佽闄嶈嚦姣?1200 瀛?1 涓紝浣嗗叏绔犱笉寰椾负闆躲€?
- 鍏告晠寮曠敤铻嶅叆锛氳嫢 Context Agent 鍦ㄦ墽琛屽寘涓帹鑽愪簡寮曠敤锛?-2 鏉★級锛屾寜鎺ㄨ崘鐨勮浇浣撳拰铻嶅叆鏂瑰紡鍐欏叆姝ｆ枃銆傚寲鐢?> 寮曠敤锛岃鑹插唴鍖?> 鏃佺櫧娉ㄩ噴銆傚垽鏂笉閫傚悎鏃跺彲璺宠繃鈥斺€?*鍏佽涓嶇敤**銆傛棤鎺ㄨ崘鏃朵笉涓诲姩寮曠敤銆傦紙璇﹁ `references/writing/classical-references.md`锛?

涓枃鎬濈淮鍐欎綔绾︽潫锛堢‖瑙勫垯锛夛細
- **绂佹"鍏堣嫳鍚庝腑"**锛氫笉寰楀厛鐢ㄨ嫳鏂囧伐绋嬪寲楠ㄦ灦锛堝 ABCDE 鍒嗘銆丼ummary/Conclusion 妗嗘灦锛夌粍缁囧唴瀹癸紝鍐嶇炕璇戞垚涓枃銆?
- **涓枃鍙欎簨鍗曞厓浼樺厛**锛氫互"鍔ㄤ綔銆佸弽搴斻€佷唬浠枫€佹儏缁€佸満鏅€佸叧绯讳綅绉?涓哄熀鏈彊浜嬪崟鍏冿紝涓嶄娇鐢ㄨ嫳鏂囩粨鏋勬爣绛鹃┍鍔ㄦ鏂囩敓鎴愩€?
- **绂佹鑻辨枃缁撹璇濇湳**锛氭鏂囥€佸鏌ヨ鏄庛€佹鼎鑹茶鏄庛€佸彉鏇存憳瑕併€佹渶缁堟姤鍛婁腑涓嶅緱鍑虹幇 Overall / PASS / FAIL / Summary / Conclusion 绛夎嫳鏂囩粨璁烘爣棰樸€?
- **鑻辨枃浠呴檺鏈哄櫒鏍囪瘑**锛欳LI flag锛坄--fast`锛夈€乧hecker id锛坄consistency-checker`锛夈€丏B 瀛楁鍚嶏紙`anti_ai_force_check`锛夈€丣SON 閿悕绛変笉鍙敼鐨勬帴鍙ｅ悕淇濇寔鑻辨枃锛屽叾浣欎竴寰嬩娇鐢ㄧ畝浣撲腑鏂囥€?

U+FFFD 缂栫爜楠岃瘉锛堝啓鍏ュ悗绔嬪嵆鎵ц锛夛細
```bash
python -c "
import glob, pathlib, sys
files = glob.glob('${PROJECT_ROOT}/姝ｆ枃/绗?{chapter_padded}绔?.md')
if not files: sys.exit('No chapter file found')
t = pathlib.Path(files[0]).read_text(encoding='utf-8')
n = t.count('\ufffd')
print(f'FFFD check: {n} corrupted chars in {files[0]}')
sys.exit(1 if n > 0 else 0)
"
```
鑻ユ娴嬪埌 U+FFFD锛堥€氬父鍥犱笂涓嬫枃鍘嬬缉鎴柇涓枃瀛楃锛夛紝绔嬪嵆鐢?Grep 瀹氫綅鎹熷潖浣嶇疆锛岀敤 Edit 淇锛屼慨澶嶅悗閲嶆柊楠岃瘉銆?*绂佹甯?FFFD 杩涘叆涓嬩竴姝ャ€?*

杈撳嚭锛?
- 绔犺妭鑽夌锛堝彲杩涘叆 Step 2B 鎴?Step 3锛夈€?

### Step 2B锛氶鏍奸€傞厤锛坄--fast` / `--minimal` 璺宠繃锛?

鎵ц鍓嶅姞杞斤細
```bash
cat "${SKILL_ROOT}/references/style-adapter.md"
```

纭姹傦細
- 鍙仛琛ㄨ揪灞傝浆璇戯紝涓嶆敼鍓ф儏浜嬪疄銆佷簨浠堕『搴忋€佽鑹茶涓虹粨鏋溿€佽瀹氳鍒欍€?
- 瀵光€滄ā鏉胯厰銆佽鏄庤厰銆佹満姊拌厰鈥濆仛瀹氬悜鏀瑰啓锛屼负 Step 4 鐣欏嚭闂淇绌洪棿銆?

杈撳嚭锛?
- 椋庢牸鍖栨鏂囷紙瑕嗙洊鍘熺珷鑺傛枃浠讹級銆?

U+FFFD 缂栫爜楠岃瘉锛堝悓 Step 2A锛岄鏍艰浆璇戝悗鍐嶆鎵ц锛岀‘淇濊浆璇戞湭寮曞叆鎹熷潖锛夈€?

### Step 3锛氬鏌ワ紙鍏ㄩ噺瀹℃煡锛屽繀椤荤敱 Task 瀛愪唬鐞嗘墽琛岋級

鎵ц鍓嶅姞杞斤細
```bash
cat "${SKILL_ROOT}/references/step-3-review-gate.md"
```

璋冪敤绾︽潫锛?
- 蹇呴』鐢?`Task` 璋冪敤瀹℃煡 subagent锛岀姝富娴佺▼浼€犲鏌ョ粨璁恒€?
- **鏍囧噯/--fast 妯″紡蹇呴』 5+5 鍒嗘壒鍚姩**锛堣瑙?`step-3-review-gate.md`锛夛紝绂佹 10 涓?checker 鍚屾椂骞跺彂銆?
- 蹇呴』绛夊緟鍏ㄩ儴 checker 杩斿洖鍚庢墠鑳界粺涓€鑱氬悎 `issues/severity/overall_score`銆?
- **绂佹鍦ㄤ换浣?checker 浠嶅湪杩愯鏃惰繘鍏?Step 4**銆傚嵆浣垮閮ㄥ鏌ュ凡瀹屾垚锛屽唴閮?checker 鏈叏閮ㄨ繑鍥炰篃涓嶅緱寮€濮嬫鼎鑹层€?

瀹℃煡鍣紙鏍囧噯妯″紡鍏ㄩ儴鎵ц锛?+5 鍒嗘壒锛夛細
- Batch 1锛堟牳蹇冧紭鍏堬紝5涓苟鍙戯級锛?
  - `consistency-checker`锛堣瀹氫竴鑷存€э級
  - `continuity-checker`锛堣繛璐€э級
  - `ooc-checker`锛堜汉鐗㎡OC锛?
  - `reader-pull-checker`锛堣拷璇诲姏锛?
  - `high-point-checker`锛堢埥鐐瑰瘑搴︼級
- Batch 2锛圔atch 1 鍏ㄩ儴杩斿洖鍚庡惎鍔紝5涓苟鍙戯級锛?
  - `pacing-checker`锛堣妭濂忓钩琛★級
  - `dialogue-checker`锛堝璇濊川閲忥級
  - `density-checker`锛堜俊鎭瘑搴︼級
  - `prose-quality-checker`锛堟枃绗旇川鎰燂級
  - `emotion-checker`锛堟儏鎰熻〃鐜帮級

妯″紡璇存槑锛?
- 鏍囧噯/`--fast`锛氬叏閲?10 涓鏌ュ櫒锛?+5 鍒嗘壒鎵ц銆?
- `--minimal`锛氬浐瀹氭牳蹇?3 涓紙consistency/continuity/ooc锛夛紝鍗曟壒骞跺彂銆?

瀹℃煡鎸囨爣钀藉簱锛堝繀鍋氾級锛?
```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index save-review-metrics --data "@${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json"
```

review_metrics 瀛楁绾︽潫锛堝綋鍓嶅伐浣滄祦绾﹀畾鍙紶浠ヤ笅瀛楁锛夛細
```json
{
  "start_chapter": 100,
  "end_chapter": 100,
  "overall_score": 85.0,
  "dimension_scores": {"鐖界偣瀵嗗害": 85, "璁惧畾涓€鑷存€?: 80, "鑺傚鎺у埗": 78, "浜虹墿濉戦€?: 82, "杩炶疮鎬?: 90, "杩借鍔?: 87, "瀵硅瘽璐ㄩ噺": 83, "淇℃伅瀵嗗害": 88, "鏂囩瑪璐ㄦ劅": 82, "鎯呮劅琛ㄧ幇": 80},
  "severity_counts": {"critical": 0, "high": 1, "medium": 2, "low": 0},
  "critical_issues": ["闂鎻忚堪"],
  "report_file": "瀹℃煡鎶ュ憡/绗?100绔犲鏌ユ姤鍛?md",
  "notes": "鍗曚釜瀛楃涓诧紱selected_checkers / timeline_gate / anti_ai_force_check 绛夋墿灞曚俊鎭帇鎴愬崟琛屾枃鏈啓鍏ユ瀛楁"
}
```
- `notes` 鍦ㄥ綋鍓嶆墽琛屽绾︿腑蹇呴』鏄崟涓瓧绗︿覆锛屼笉寰椾紶鍏ュ璞℃垨鏁扮粍銆?
- 褰撳墠宸ヤ綔娴佷笉棰濆浼犲叆鍏跺畠椤跺眰瀛楁锛涜剼鏈晶鏈湪姝ゅ鍋氭柊澧炵‖鏍￠獙銆?

纭姹傦細
- `--minimal` 涔熷繀椤讳骇鍑?`overall_score`銆?
- 鏈惤搴?`review_metrics` 涓嶅緱杩涘叆 Step 5銆?
- `overall_score` 蹇呴』鎸?`step-3-review-gate.md` 鐨?鍐呭閮ㄥ垎鏁板悎骞惰鍒?璁＄畻锛歚round(internal * 0.6 + external_avg * 0.4)`銆傝嫢 Step 3.5 鍏ㄩ儴澶辫触鎴栬妯″紡璺宠繃锛坄--minimal`锛夛紝鍒欓€€鍖栦负绾唴閮ㄥ垎鏁般€?

### Step 3.5锛氬閮ㄦā鍨嬪鏌ワ紙涓?Step 3 骞惰鎴栫揣鎺ユ墽琛岋級

鎵ц鍓嶅繀椤诲姞杞斤細
```bash
cat "${SKILL_ROOT}/references/step-3.5-external-review.md"
```

纭姹傦細
- **蹇呴』浣跨敤 `--model-key all` 涓€娆℃€ф墽琛屽叏閮?9 妯″瀷**锛岀姝㈡墜鍔ㄩ€愪釜璋冪敤锛堥槻姝㈤仐婕忔ā鍨嬶級銆?
- 鏍稿績3妯″瀷蹇呴』鍏ㄩ儴鎴愬姛锛岃ˉ鍏?妯″瀷澶辫触涓嶉樆濉炪€?
- 鎸?reference 鏂囦欢涓殑 Prompt 妯℃澘鏋勫缓 system 娑堟伅銆?
- 姣忔 API 璋冪敤鍚庨獙璇佽矾鐢憋紙妫€鏌?response.model 瀛楁锛夈€?
- 鏍稿績妯″瀷鍥涚骇 fallback 閾撅細nextapi(2娆? 鈫?healwrap(2娆? 鈫?codexcc(1娆? 鈫?纭呭熀娴佸姩(鍏滃簳)銆?
- 杈撳嚭 JSON 蹇呴』鍖呭惈 model_actual銆乺outing_verified銆乸rovider_chain銆乧ross_validation銆?
- 鐢熸垚瀹℃煡鎶ュ憡蹇呴』鍖呭惈 9 妯″瀷 脳 10 缁村害璇勫垎鐭╅樀 + 鍏辫瘑闂 + Step 4 淇娓呭崟銆?

**涓婁笅鏂囨枃浠跺噯澶囷紙璋冪敤鑴氭湰鍓嶅繀椤诲畬鎴愶級**锛?

鑴氭湰浠?`{PROJECT_ROOT}/.webnovel/tmp/external_context_ch{chapter_padded}.json` 鍔犺浇涓婁笅鏂囥€?*鑻ユ枃浠朵笉瀛樺湪锛岃剼鏈皢鎶ラ敊閫€鍑猴紙exit 1锛?*銆備富娴佺▼蹇呴』鍦ㄨ皟鐢ㄨ剼鏈墠鏋勫缓姝ゆ枃浠讹紝鍖呭惈 9 涓瓧娈碉細

```bash
# 鏀堕泦璁惧畾闆嗐€佸ぇ绾层€佸墠绔犳鏂囷紝鍐欏叆 context JSON
python -c "
import json, pathlib
pr = pathlib.Path('${PROJECT_ROOT}')
def read(p):
    f = pr / p
    return f.read_text(encoding='utf-8') if f.exists() else ''
ctx = {
    'outline_excerpt': read('澶х翰/鎬荤翰.md')[:3000],
    'protagonist_card': read('璁惧畾闆?涓昏鍗?md'),
    'golden_finger_card': read('璁惧畾闆?閲戞墜鎸囪璁?md'),
    'female_lead_card': read('璁惧畾闆?濂充富鍗?md'),
    'villain_design': read('璁惧畾闆?鍙嶆淳璁捐.md'),
    'power_system': read('璁惧畾闆?鍔涢噺浣撶郴.md'),
    'world_settings': read('璁惧畾闆?涓栫晫瑙?md')[:5000],
    'protagonist_state': json.loads((pr/'.webnovel/state.json').read_text(encoding='utf-8')).get('protagonist_state',{}),
    'prev_chapters_text': '\\n---\\n'.join(
        f.read_text(encoding='utf-8') for f in sorted((pr/'姝ｆ枃').glob('绗?绔?.md'))[:${chapter_num}]
    )[:15000]
}
out = pr / '.webnovel/tmp/external_context_ch${chapter_padded}.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Context written: {out} ({out.stat().st_size} bytes)')
"
```

鑻ヤ笂杩拌剼鏈け璐ワ紝鎵嬪姩浠庤瀹氶泦鏂囦欢璇诲彇骞剁敤 `Write` 宸ュ叿鍐欏叆 JSON銆?*绂佹璺宠繃姝ゆ楠ょ洿鎺ヨ皟鐢?external_review.py**銆?

璋冪敤鍛戒护锛?
```bash
python -X utf8 "${SCRIPTS_DIR}/external_review.py" \
  --project-root "${PROJECT_ROOT}" \
  --chapter {chapter_num} \
  --mode dimensions \
  --model-key all
```
鈿狅笍 鑴氭湰浠呮敮鎸侊細`--project-root`, `--chapter`, `--mode`, `--model-key`, `--models`, `--max-concurrent`, `--rpm-override`銆備笉瑕佷紶鍏朵粬鍙傛暟銆?

杈撳嚭锛?
- 姣忔ā鍨嬩竴涓?`.webnovel/tmp/external_review_{model_key}_ch{NNNN}.json`锛堝叡9涓枃浠讹級
- 瀹℃煡鎶ュ憡 `瀹℃煡鎶ュ憡/绗瑊NNNN}绔犲鏌ユ姤鍛?md`锛堝惈 9 妯″瀷 脳 10 缁村害鐭╅樀锛?

### Step 3+3.5 瀹屾垚闂搁棬锛堣繘鍏?Step 4 鍓嶅繀椤婚€氳繃锛?

**纭鍒欙細Step 4 涓嶅緱鍦?Step 3 鎴?Step 3.5 鏈変换浣曞瓙浠诲姟浠嶅湪杩愯鏃跺紑濮嬨€?*

楠岃瘉鏂瑰紡锛?
1. 閫愪竴妫€鏌ユ墍鏈?Step 3 鍐呴儴 checker 鐨?Task 鐘舵€侊紙`TaskOutput` 鎴栫瓑浠疯疆璇級锛岀‘璁ゆ瘡涓?checker 閮藉凡杩斿洖缁撴灉锛堥潪绌鸿緭鍑猴級銆?
2. 纭 Step 3.5 澶栭儴瀹℃煡鑴氭湰宸查€€鍑轰笖 9 涓?`external_review_{model_key}_ch{NNNN}.json` 鏂囦欢宸茬敓鎴愩€?
3. 鎸?`step-3-review-gate.md` 鐨?鍐呭閮ㄥ垎鏁板悎骞惰鍒?璁＄畻 `overall_score`锛堥渶瑕佸唴閮?+ 澶栭儴閮芥湁鍒嗘暟锛夈€?
4. 鐢熸垚瀹℃煡鎶ュ憡锛堝惈鍐呴儴10缁村害 + 澶栭儴9妯″瀷脳10缁村害鐭╅樀锛夈€?
5. 钀藉簱 `review_metrics`銆?

**浠ヤ笂 5 姝ュ叏閮ㄥ畬鎴愬悗锛屾柟鍙繘鍏?Step 4銆傜瓑寰呮槸娴佺▼鐨勪竴閮ㄥ垎銆?*

**Step 3鈫? 闂搁棬寮哄埗楠岃瘉**锛堝湪鏍囪 Step 3 瀹屾垚鍓嶅繀椤绘墽琛岋級锛?
1. 瀵规瘡涓凡鍚姩鐨勫唴閮?checker Task 璋冪敤 `TaskOutput`锛岀‘璁よ緭鍑洪潪绌恒€傝嫢浠讳竴 checker 杈撳嚭涓虹┖锛岀户缁瓑寰咃紙杞闂撮殧30s锛屾瘡鎵规渶澶氱瓑寰?0鍒嗛挓锛屾€昏秴鏃?0鍒嗛挓锛夈€傝秴鏃朵粛鏈繑鍥炵殑 checker 鏍囪涓?timeout 骞跺啓鍏ュ鏌ユ姤鍛娿€傛敞鎰忥細5+5 鍒嗘壒妯″紡涓嬶紝Batch 1 鍏ㄩ儴杩斿洖鍚庡啀鍚姩 Batch 2锛屾瘡鎵圭嫭绔嬭鏃躲€?
2. 妫€鏌?`.webnovel/tmp/external_review_{model}_ch{NNNN}.json`锛氭牳蹇?妯″瀷鏂囦欢蹇呴』瀛樺湪涓旈潪绌猴紝琛ュ厖妯″瀷缂哄け鍙帴鍙椼€?
3. 鑱氬悎鍒嗘暟锛氬唴閮?0涓?checker 鍙栧钩鍧囷紱澶栭儴宸叉垚鍔熸ā鍨嬪彇骞冲潎锛涘悎骞?`round(internal * 0.6 + external * 0.4)`銆?
4. 鍐欏鏌ユ姤鍛?+ 钀藉簱 review_metrics銆?
**杩濊鍚庢灉**锛氳烦杩囨楠岃瘉鐩存帴杩涘叆 Step 4锛孲tep 6 瀹¤ A2 妫€鏌ラ」灏嗘娴嬪埌 checker 鍧嶇缉骞跺彲鑳?block 鎻愪氦銆?

### Step 4锛氭鼎鑹诧紙闂淇浼樺厛锛?

鎵ц鍓嶅繀椤诲姞杞斤細
```bash
cat "${SKILL_ROOT}/references/polish-guide.md"
cat "${SKILL_ROOT}/references/writing/typesetting.md"
```

鎵ц椤哄簭锛?
1. 淇 `critical`锛堝繀椤伙級
2. 淇 `high`锛堜笉鑳戒慨澶嶅垯璁板綍 deviation锛?
3. 澶勭悊 `medium/low`锛堟寜鏀剁泭鎷╀紭锛?
4. 鎵ц Anti-AI 涓?No-Poison 鍏ㄦ枃缁堟锛堝繀椤昏緭鍑?`anti_ai_force_check: pass/fail`锛?

杈撳嚭锛?
- 娑﹁壊鍚庢鏂囷紙瑕嗙洊绔犺妭鏂囦欢锛?
- 鍙樻洿鎽樿锛堣嚦灏戝惈锛氫慨澶嶉」銆佷繚鐣欓」銆乨eviation銆乣anti_ai_force_check`锛?

### Step 5锛欴ata Agent锛堢姸鎬佷笌绱㈠紩鍥炲啓锛?

浣跨敤 Task 璋冪敤 `data-agent`锛屽弬鏁帮細
- `chapter`
- `chapter_file` 蹇呴』浼犲叆瀹為檯绔犺妭鏂囦欢璺緞锛涜嫢璇︾粏澶х翰宸叉湁绔犺妭鍚嶏紝浼樺厛浼?`姝ｆ枃/绗瑊chapter_padded}绔?{title_safe}.md`锛屽惁鍒欎紶 `姝ｆ枃/绗瑊chapter_padded}绔?md`
- `review_score=Step 3 overall_score`
- `project_root`
- `storage_path=.webnovel/`
- `state_file=.webnovel/state.json`

Data Agent 榛樿瀛愭楠わ紙鍏ㄩ儴鎵ц锛夛細
- A. 鍔犺浇涓婁笅鏂?
- B. AI 瀹炰綋鎻愬彇
- C. 瀹炰綋娑堟
- D. 鍐欏叆 state/index
- E. 鍐欏叆绔犺妭鎽樿
- F. AI 鍦烘櫙鍒囩墖
- G. RAG 鍚戦噺绱㈠紩锛坄rag index-chapter --scenes ...`锛?
- H. 椋庢牸鏍锋湰璇勪及锛坄style extract --scenes ...`锛屼粎 `review_score >= 80` 鏃讹級
- I. 鍊哄姟鍒╂伅锛堥粯璁よ烦杩囷級
- J. 鐢熸垚澶勭悊鎶ュ憡锛堝繀椤昏褰?A-I 姣忔鑰楁椂锛涘啓鍏?`.webnovel/observability/data_agent_timing.jsonl`锛?
- K. 璁惧畾闆嗗悓姝ユ鏌ワ紙姣忕珷鎵ц锛宐est-effort锛屽け璐ヤ笉闃绘柇锛?

`--scenes` 鏉ユ簮浼樺厛绾э紙G/H 姝ラ鍏辩敤锛夛細
1. 浼樺厛浠?`index.db` 鐨?scenes 璁板綍鑾峰彇锛圫tep F 鍐欏叆鐨勭粨鏋滐級
2. 鍏舵鎸?`start_line` / `end_line` 浠庢鏂囧垏鐗囨瀯閫?
3. 鏈€鍚庡厑璁稿崟鍦烘櫙閫€鍖栵紙鏁寸珷浣滀负涓€涓?scene锛?

Step 5 澶辫触闅旂瑙勫垯锛?
- 鑻?G/H 澶辫触鍘熷洜鏄?`--scenes` 缂哄け銆乻cene 涓虹┖銆乻cene JSON 鏍煎紡閿欒锛氬彧琛ヨ窇 G/H 瀛愭楠わ紝涓嶅洖婊氭垨閲嶈窇 Step 1-4銆?
- 鑻?A-E 澶辫触锛坰tate/index/summary 鍐欏叆澶辫触锛夛細浠呴噸璺?Step 5锛屼笉鍥炴粴宸查€氳繃鐨?Step 1-4銆?
- 绂佹鍥?RAG/style 瀛愭楠ゅけ璐ヨ€岄噸璺戞暣涓啓浣滈摼銆?

鎵ц鍚庢鏌ワ紙鏈€灏忕櫧鍚嶅崟锛夛細
- `.webnovel/state.json`
- `.webnovel/index.db`
- `.webnovel/summaries/ch{chapter_padded}.md`
- `.webnovel/observability/data_agent_timing.jsonl`锛堣娴嬫棩蹇楋級

**鏁版嵁瀹屾暣鎬у悗楠岃瘉锛圫tep 5 瀹屾垚鍚庡繀椤绘墽琛岋級**锛?
```python
# 鐢?Bash 鎵ц浠ヤ笅 Python 楠岃瘉锛屼换涓€椤?FAIL 鍒欏繀椤荤珛鍗宠ˉ淇?
import json, re
with open('.webnovel/state.json','r',encoding='utf-8') as f: s=json.load(f)
meta = s['chapter_meta'][f'{chapter:04d}']
# 1. checker_scores 闈炵┖
assert meta.get('checker_scores') and len(meta['checker_scores']) >= 3, 'FAIL: checker_scores empty'
# 2. word_count 鍑嗙‘锛堢敤鏍囧噯鏂规硶閲嶇畻瀵规瘮锛岃宸?=2%锛?
with open(chapter_file,'r',encoding='utf-8') as f: text=f.read()
actual = len(re.findall(r'[\u4e00-\u9fff]', text))
assert abs(meta['word_count'] - actual) / actual < 0.02, f'FAIL: word_count {meta["word_count"]} vs actual {actual}'
# 3. strand_tracker 涓?chapter_meta 涓€鑷?
history = s['strand_tracker']['history']
tracker_strand = [h for h in history if h['chapter']==chapter][0]['dominant']
assert tracker_strand == meta['strand_dominant'].lower(), f'FAIL: strand mismatch {tracker_strand} vs {meta["strand_dominant"]}'
```

鎬ц兘瑕佹眰锛?
- 璇诲彇 timing 鏃ュ織鏈€杩戜竴鏉★紱
- 褰?`TOTAL > 30000ms` 鏃讹紝杈撳嚭鏈€鎱?2-3 涓幆鑺備笌鍘熷洜璇存槑銆?

瑙傛祴鏃ュ織璇存槑锛?
- `call_trace.jsonl`锛氬灞傛祦绋嬭皟鐢ㄩ摼锛坅gent 鍚姩銆佹帓闃熴€佺幆澧冩帰娴嬬瓑绯荤粺寮€閿€锛夈€?
- `data_agent_timing.jsonl`锛欴ata Agent 鍐呴儴鍚勫瓙姝ラ鑰楁椂銆?
- 褰撳灞傛€昏€楁椂杩滃ぇ浜庡唴灞?timing 涔嬪拰鏃讹紝榛樿鍏堝綊鍥犱负 agent 鍚姩涓庣幆澧冩帰娴嬪紑閿€锛屼笉璇垽涓烘鏂囨垨鏁版嵁澶勭悊鎱€?

鍊哄姟鍒╂伅锛?
- 榛樿鍏抽棴锛屼粎鍦ㄧ敤鎴锋槑纭姹傛垨寮€鍚拷韪椂鎵ц锛堣 `step-5-debt-switch.md`锛夈€?

璁惧畾闆嗗悓姝ワ紙Step K锛夛細
- 姣忕珷鎵ц锛屾鏌ユ柊瀹炰綋/閬撳叿鐘舵€佸彉鍖?浼忕瑪/璧勪骇鍙樺姩锛岃拷鍔犲埌璁惧畾闆嗘枃浠?
- 鎵€鏈夎拷鍔犲甫 `[Ch{N}]` 绔犺妭鏍囨敞
- 澶辫触涓嶉樆鏂祦绋?

### Step 6锛氬璁￠椄闂紙Audit Gate锛?

> **瀹氫綅**锛歋tep 6 鏄?git 鎻愪氦鍓嶇殑鏈€鍚庝竴閬撻槻绾匡紝璺ㄦ楠?璺ㄤ骇鐗?璺ㄧ珷瀹￠摼璺湡瀹炴€с€佹壙璇哄厬鐜般€佷綔鍝佽繛缁€с€傚畬鏁磋鑼冭 `references/step-6-audit-gate.md` 涓?`references/step-6-audit-matrix.md`锛坅udit-agent 蹇呰锛夈€?

Step 6 涓€娆¤皟鐢ㄧ敱涓ら儴鍒嗙粍鎴愶紝**蹇呴』鍏ㄩ儴瀹屾垚**锛?

**Part 1 鈥?CLI 缁撴瀯瀹¤锛堝揩閫熻矾寰勶紝< 5s锛?*

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  audit chapter --chapter ${chapter_num} --mode ${mode} \
  --out "${PROJECT_ROOT}/.webnovel/tmp/audit_layer_abg_ch${chapter_padded}.json"
```

瀹屾垚 Layer A锛堣繃绋嬬湡瀹炴€э級銆丩ayer B锛堣法浜х墿涓€鑷存€э級銆丩ayer G锛堣法绔犺秼鍔匡級鐨勭‘瀹氭€ф鏌ャ€傞€€鍑虹爜锛?=pass / 1=critical fail / 2=warnings / 3=CLI 閿欒銆?

**Part 2 鈥?audit-agent 娣卞害瀹¤锛?0-300s锛?*

```
Task(audit-agent, {
  chapter: <chapter_num>,
  project_root: <PROJECT_ROOT>,
  mode: <standard|fast|minimal>,
  chapter_file: <姝ｆ枃/绗琋NNN绔?*.md>,
  time_budget_seconds: 300
})
```

audit-agent 鑷姩璇诲彇 Part 1 鐨?JSON 杈撳嚭锛屽畬鎴?Layer C / D / E / F 鍒ゆ柇鎬ф鏌ワ紝鑱氬悎鎵€鏈夊眰绾э紝浜у嚭鏈€缁?`.webnovel/audit_reports/ch{NNNN}.json` 涓庝笅绔?`editor_notes/ch{NNNN+1}_prep.md`銆?

**鍐宠瑙勫垯**锛?
- `decision == block` 鈫?鎸?blocking_issues 鐨?remediation 淇锛岄噸璺戝搴旀楠わ紝**涓嶅緱杩涘叆 Step 7**
- `decision == approve_with_warnings` 鈫?璁板綍 warnings锛岃繘鍏?Step 7锛宑ommit message 闄?`[audit:warn:layerX]`
- `decision == approve` 鈫?鐩存帴杩涘叆 Step 7

**纭姹?*锛?
- Part 1 涓?Part 2 閮藉繀椤诲畬鎴愶紱鍗充娇 Part 1 澶辫触锛孭art 2 浠嶈鎵ц浠ョ粰鍑哄畬鏁磋瘖鏂?
- `audit_reports/ch{NNNN}.json` 蹇呴』鎴愬姛鍐欏嚭锛堜笉鍙烦杩?editor_notes 涓?trend 鏃ュ織锛?
- audit-agent 鍙涓嶅啓锛堥櫎瀹¤浜х墿锛夛紝绂佹淇敼姝ｆ枃/璁惧畾闆?state
- Step 6 瓒呮椂锛?00s锛夎涓烘湭瀹屾垚锛宐lock 杩涘叆 Step 7
- 绂佹寮哄埗璺宠繃锛堥櫎闈炵敤鎴锋樉寮忕‘璁や笖璁板綍鍒?forced_skip 瀛楁锛?

### Step 7锛欸it 澶囦唤锛堝彲澶辫触浣嗛渶璇存槑锛?

```bash
git add .
git -c i18n.commitEncoding=UTF-8 commit -m "绗瑊chapter_num}绔? {title}"
```

瑙勫垯锛?
- 鎻愪氦鏃舵満锛歋tep 6 瀹¤閫氳繃鍚庢渶鍚庢墽琛屻€?
- 鎻愪氦淇℃伅榛樿涓枃锛屾牸寮忥細`绗瑊chapter_num}绔? {title}`锛涜嫢 Step 6 鍐宠涓?`approve_with_warnings`锛岃拷鍔?`[audit:warn:layerX]` 鍚庣紑銆?
- 鑻?commit 澶辫触锛屽繀椤荤粰鍑哄け璐ュ師鍥犱笌鏈彁浜ゆ枃浠惰寖鍥淬€?

## 鍏呭垎鎬ч椄闂紙蹇呴』閫氳繃锛?

鏈弧瓒充互涓嬫潯浠跺墠锛屼笉寰楃粨鏉熸祦绋嬶細

1. 绔犺妭姝ｆ枃鏂囦欢瀛樺湪涓旈潪绌猴細`姝ｆ枃/绗瑊chapter_padded}绔?{title_safe}.md` 鎴?`姝ｆ枃/绗瑊chapter_padded}绔?md`
2. Step 3 宸蹭骇鍑?`overall_score` 涓?`review_metrics` 鎴愬姛钀藉簱
3. Step 3.5 澶栭儴瀹℃煡宸插畬鎴愶紙鏍稿績3妯″瀷蹇呴』鎴愬姛锛夛紙`--minimal` 妯″紡璺宠繃姝ゆ潯浠讹級
4. 瀹℃煡鎶ュ憡 `.md` 鏂囦欢宸茬敓鎴愶紙鏍囧噯/`--fast` 妯″紡鍚唴閮?0缁村害鍒嗘暟+澶栭儴9妯″瀷脳10缁村害璇勫垎鐭╅樀锛沗--minimal` 妯″紡浠呭惈鍐呴儴3缁村害鍒嗘暟锛?
5. Step 4 宸插鐞嗗叏閮?`critical`锛宍high` 鏈慨椤规湁 deviation 璁板綍
6. Step 4 鐨?`anti_ai_force_check=pass`锛堝熀浜庡叏鏂囨鏌ワ紱fail 鏃朵笉寰楄繘鍏?Step 5锛?
7. Step 5 宸插洖鍐?`state.json`銆乣index.db`銆乣summaries/ch{chapter_padded}.md`
8. Step 6 瀹¤浜х墿榻愬叏锛歚audit_reports/ch{chapter_padded}.json`銆乣editor_notes/ch{next_padded}_prep.md`銆乣observability/chapter_audit.jsonl` 杩藉姞涓€琛岋紱audit decision 鈭?{approve, approve_with_warnings}
9. Step 7 Git 宸叉彁浜?
10. 鑻ュ紑鍚€ц兘瑙傛祴锛屽凡璇诲彇鏈€鏂?timing 璁板綍骞惰緭鍑虹粨璁?

## 楠岃瘉涓庝氦浠?

鎵ц妫€鏌ワ細

```bash
test -f "${PROJECT_ROOT}/.webnovel/state.json"
ls "${PROJECT_ROOT}/姝ｆ枃/绗?{chapter_padded}绔?*.md >/dev/null 2>&1
test -f "${PROJECT_ROOT}/.webnovel/summaries/ch${chapter_padded}.md"
test -f "${PROJECT_ROOT}/.webnovel/audit_reports/ch${chapter_padded}.json"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" audit check-decision --chapter ${chapter_num} --require approve,approve_with_warnings
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index get-recent-review-metrics --limit 1
tail -n 1 "${PROJECT_ROOT}/.webnovel/observability/data_agent_timing.jsonl" || true
tail -n 1 "${PROJECT_ROOT}/.webnovel/observability/chapter_audit.jsonl" || true
```

鎴愬姛鏍囧噯锛?
- 绔犺妭鏂囦欢銆佹憳瑕佹枃浠躲€佺姸鎬佹枃浠堕綈鍏ㄤ笖鍐呭鍙銆?
- 瀹℃煡鍒嗘暟鍙拷婧紝`overall_score` 涓?Step 5 杈撳叆涓€鑷淬€?
- 娑﹁壊鍚庢湭鐮村潖澶х翰涓庤瀹氱害鏉熴€?

## 澶辫触澶勭悊锛堟渶灏忓洖婊氾級

瑙﹀彂鏉′欢锛?
- 绔犺妭鏂囦欢缂哄け鎴栫┖鏂囦欢锛?
- 瀹℃煡缁撴灉鏈惤搴擄紱
- Data Agent 鍏抽敭浜х墿缂哄け锛?
- 娑﹁壊寮曞叆璁惧畾鍐茬獊銆?

鎭㈠娴佺▼锛?
1. 浠呴噸璺戝け璐ユ楠わ紝涓嶅洖婊氬凡閫氳繃姝ラ銆?
2. 甯歌鏈€灏忎慨澶嶏細
   - 瀹℃煡缂哄け锛氬彧閲嶈窇 Step 3 骞惰惤搴擄紱
   - 澶栭儴瀹℃煡缂哄け/澶辫触锛氬彧閲嶈窇 Step 3.5锛堟牳蹇冩ā鍨嬫寜 fallback 閾鹃噸璇曪級锛?
   - `anti_ai_force_check=fail`锛氱暀鍦?Step 4 缁х画鏀瑰啓鐩村埌 pass锛屼笉鍥為€€涔熶笉璺宠繃锛?
   - 娑﹁壊澶辩湡锛氭仮澶?Step 2A 杈撳嚭骞堕噸鍋?Step 4锛?
   - 鎽樿/鐘舵€佺己澶憋細鍙噸璺?Step 5锛?
   - Step 6 audit block锛氭寜 `audit_reports/ch{NNNN}.json` 鐨?`blocking_issues` 閫愰」 remediation锛堥€氬父鍥炲埌 Step 1/3/3.5/4/5锛夛紝淇鍚庨噸璺?Step 6锛?
   - Step 6 audit 瓒呮椂锛氶噸璺?audit-agent锛堝閲忔ā寮忥紝浠呰窇鏈畬鎴?layers锛夛紱
3. 閲嶆柊鎵ц鈥濋獙璇佷笌浜や粯鈥濆叏閮ㄦ鏌ワ紝閫氳繃鍚庣粨鏉熴€?
