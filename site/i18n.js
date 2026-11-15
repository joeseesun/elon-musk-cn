/* 马斯克全访谈 · 界面多语言（i18n）。
 * 只翻译界面 chrome（导航 / 按钮 / 标签 / 提示 / 占位符 / aria），
 * 绝不碰内容：中文精读正文、英文文稿、语录、标题、日期、数字。
 * 语言选择持久化到 localStorage；自动识别用浏览器语言（见 detectLang）。
 * 暴露 window.I18N = { t, lang, setLang, supported, observe }。
 */
(function () {
  'use strict';

  // 语言顺序与 DICT 中每个条目的数组顺序一致
  var ORDER = ['zh', 'zh-TW', 'en', 'de', 'fr', 'es', 'ko', 'ja'];
  var LABELS = {
    'zh': '简体中文', 'zh-TW': '繁體中文', 'en': 'English', 'de': 'Deutsch',
    'fr': 'Français', 'es': 'Español', 'ko': '한국어', 'ja': '日本語'
  };
  var SHORT = {
    'zh': '中', 'zh-TW': '繁', 'en': 'EN', 'de': 'DE', 'fr': 'FR',
    'es': 'ES', 'ko': '한', 'ja': '日'
  };
  var LANG_ATTR = {
    'zh': 'zh-CN', 'zh-TW': 'zh-TW', 'en': 'en', 'de': 'de',
    'fr': 'fr', 'es': 'es', 'ko': 'ko', 'ja': 'ja'
  };

  // 简体中文原文 -> [zh, zh-TW, en, de, fr, es, ko, ja]
  // 简体项留空字符串时回退到 key 本身（即原文）。
  var DICT = {
    // ---- 无障碍标签 / 二维码 ----
    '频道': ['', '頻道', 'Channels', 'Kanäle', 'Rubriques', 'Canales', '채널', 'チャンネル'],
    '马斯克全访谈 · 中文精读全文': ['', '馬斯克全訪談 · 中文精讀全文', 'Elon Musk Interviews · Full Chinese deep-reads', 'Elon Musk Interviews · Chinesische Tiefenlesungen vollständig', 'Interviews d’Elon Musk · Lectures en chinois intégrales', 'Entrevistas de Elon Musk · Lecturas en chino completas', '일론 머스크 인터뷰 · 중국어 정독 전문', 'イーロン・マスク全インタビュー · 中国語精読全文'],
    '马斯克全访谈 · 首页': ['', '馬斯克全訪談 · 首頁', 'Elon Musk Interviews · Home', 'Elon Musk Interviews · Startseite', 'Interviews d’Elon Musk · Accueil', 'Entrevistas de Elon Musk · Inicio', '일론 머스크 인터뷰 · 홈', 'イーロン・マスク全インタビュー · ホーム'],
    '打赏二维码': ['', '打賞二維碼', 'Support QR code', 'Spenden-QR-Code', 'QR code de soutien', 'Código QR de apoyo', '후원 QR 코드', '支援用QRコード'],
    '公众号二维码': ['', '公眾號二維碼', 'WeChat QR code', 'WeChat-QR-Code', 'QR code WeChat', 'Código QR de WeChat', '위챗 QR 코드', 'WeChat QRコード'],
    '中文精读 Markdown': ['', '中文精讀 Markdown', 'Chinese deep-reads Markdown', 'Chinesische Tiefenlesungen als Markdown', 'Lectures en chinois en Markdown', 'Lecturas en chino en Markdown', '중국어 정독 Markdown', '中国語精読 Markdown'],
    '致读者': ['', '致讀者', 'To the reader', 'An die Leser', 'Au lecteur', 'Al lector', '독자에게', '読者へ'],
    // ---- 频道导航 ----
    '首页': ['', '首頁', 'Home', 'Startseite', 'Accueil', 'Inicio', '홈', 'ホーム'],
    '搜索': ['', '搜尋', 'Search', 'Suche', 'Recherche', 'Buscar', '검색', '検索'],
    '语录': ['', '語錄', 'Quotes', 'Zitate', 'Citations', 'Citas', '명언', '名言'],
    '主题': ['', '主題', 'Themes', 'Themen', 'Thèmes', 'Temas', '주제', 'テーマ'],
    '趋势': ['', '趨勢', 'Trends', 'Trends', 'Tendances', 'Tendencias', '추세', 'トレンド'],
    '数据': ['', '數據', 'Data', 'Daten', 'Données', 'Datos', '데이터', 'データ'],
    '预言': ['', '預言', 'Predictions', 'Vorhersagen', 'Prédictions', 'Predicciones', '예측', '予測'],
    '全部视频': ['', '全部影片', 'All videos', 'Alle Videos', 'Toutes les vidéos', 'Todos los videos', '모든 영상', 'すべての動画'],
    '中文精读': ['', '中文精讀', 'Chinese deep-reads', 'Chinesische Tiefenlesung', 'Lectures en chinois', 'Lecturas en chino', '중국어 정독', '中国語精読'],
    '文稿搜索': ['', '文稿搜尋', 'Transcript search', 'Transkriptsuche', 'Recherche de transcriptions', 'Búsqueda de transcripción', '대본 검색', '文字起こし検索'],
    '话题趋势': ['', '話題趨勢', 'Topic trends', 'Thementrends', 'Tendances des sujets', 'Tendencias de temas', '주제 추세', '話題トレンド'],
    '档案数据': ['', '檔案數據', 'Archive stats', 'Archivstatistik', 'Statistiques des archives', 'Estadísticas del archivo', '아카이브 통계', 'アーカイブ統計'],
    '视频目录': ['', '影片目錄', 'Video archive', 'Videoarchiv', 'Catalogue des vidéos', 'Catálogo de vídeos', '영상 목록', '動画一覧'],
    '预言追踪': ['', '預言追蹤', 'Predictions tracker', 'Vorhersagen-Verfolgung', 'Suivi des prédictions', 'Rastreador de predicciones', '예측 추적', '予測トラッカー'],
    // ---- 页脚 ----
    '浏览': ['', '瀏覽', 'Browse', 'Stöbern', 'Parcourir', 'Explorar', '둘러보기', '見る'],
    '订阅': ['', '訂閱', 'Subscribe', 'Abonnieren', "S'abonner", 'Suscribirse', '구독', '購読'],
    '关于': ['', '關於', 'About', 'Über', 'À propos', 'Acerca de', '소개', '概要'],
    '支持这个项目': ['', '支持這個專案', 'Support this project', 'Dieses Projekt unterstützen', 'Soutenir ce projet', 'Apoyar este proyecto', '이 프로젝트 후원', 'このプロジェクトを支援'],
    'RSS 全文订阅': ['', 'RSS 全文訂閱', 'RSS full-text feed', 'RSS-Volltext-Feed', 'Flux RSS intégral', 'Feed RSS completo', 'RSS 전문 구독', 'RSS 全文購読'],
    '复制 RSS 地址': ['', '複製 RSS 網址', 'Copy RSS URL', 'RSS-URL kopieren', "Copier l'URL RSS", 'Copiar URL RSS', 'RSS 주소 복사', 'RSS URL をコピー'],
    '数据源 Elon Musk Archive': ['', '資料來源 Elon Musk Archive', 'Source: Elon Musk Archive', 'Quelle: Elon Musk Archive', 'Source : Elon Musk Archive', 'Fuente: Elon Musk Archive', '출처: Elon Musk Archive', '出典: Elon Musk Archive'],
    '下载语料': ['', '下載語料', 'Download corpus', 'Korpus herunterladen', 'Télécharger le corpus', 'Descargar el corpus', '말뭉치 다운로드', 'コーパスをダウンロード'],
    '开源代码': ['', '開源程式碼', 'Source code', 'Quellcode', 'Code source', 'Código fuente', '소스 코드', 'ソースコード'],
    '免责声明': ['', '免責聲明', 'Disclaimer', 'Haftungsausschluss', 'Avertissement', 'Aviso legal', '면책 조항', '免責事項'],
    '乔木推荐': ['', '喬木推薦', 'Qiaomu recommends', 'Qiaomu empfiehlt', 'Qiaomu recommande', 'Qiaomu recomienda', 'Qiaomu 추천', 'Qiaomu おすすめ'],
    '把马斯克 28 年的公开访谈，用中文认真读一遍。': ['', '把馬斯克 28 年的公開訪談，用中文認真讀一遍。', 'Musk’s public interviews over 28 years, read carefully in Chinese.', 'Musks öffentliche Interviews aus 28 Jahren – sorgfältig auf Chinesisch gelesen.', '28 ans d’entretiens publics de Musk, lus attentivement en chinois.', '28 años de entrevistas públicas de Musk, leídas atentamente en chino.', '28년간의 머스크 공개 인터뷰를 중국어로 정성껏 읽기.', '28年分のマスクの公開インタビューを中国語で丁寧に読む。'],
    '安装为应用': ['', '安裝為應用程式', 'Install app', 'App installieren', "Installer l'application", 'Instalar la app', '앱 설치', 'アプリをインストール'],
    '打赏支持': ['', '打賞支持', 'Support author', 'Autor unterstützen', 'Soutenir l’auteur', 'Apoyar al autor', '작가 후원', '著者を支援'],
    '关注公众号': ['', '關注公眾號', 'Follow on WeChat', 'WeChat folgen', 'Suivre sur WeChat', 'Seguir en WeChat', '위챗 팔로우', 'WeChatをフォロー'],
    '谢谢你的支持': ['', '謝謝你的支持', 'Thank you for your support', 'Danke für Ihre Unterstützung', 'Merci pour votre soutien', 'Gracias por tu apoyo', '후원해 주셔서 감사합니다', 'ご支援ありがとうございます'],
    '每一份打赏都会变成更多认真校过的精读': ['', '每一份打賞都會變成更多認真校過的精讀', 'Every contribution becomes another carefully edited deep-read', 'Jede Spende wird zu einer weiteren sorgfältig lektorierten Tiefenlesung', 'Chaque don devient une nouvelle lecture approfondie soigneusement relue', 'Cada donación se convierte en otra lectura profunda cuidadosamente revisada', '모든 후원은 정교하게 다듬은 정독 한 편이 됩니다', 'ご支援は丁寧に校閲された精読一篇につながります'],
    '微信扫一扫': ['', '微信掃一掃', 'Scan with WeChat', 'Mit WeChat scannen', 'Scanner avec WeChat', 'Escanear con WeChat', '위챗으로 스캔', 'WeChatでスキャン'],
    '添加到主屏幕': ['', '新增至主畫面', 'Add to Home Screen', 'Zum Home-Bildschirm hinzufügen', "Ajouter à l'écran d'accueil", 'Añadir a la pantalla de inicio', '홈 화면에 추가', 'ホーム画面に追加'],
    '像应用一样打开，读过的文章离线也能看': ['', '像應用程式一樣開啟，讀過的文章離線也能看', 'Open like an app; articles you read work offline', 'Wie eine App öffnen – gelesene Artikel funktionieren offline', 'Ouvrir comme une appli ; les articles lus sont disponibles hors ligne', 'Abre como una app; los artículos leídos funcionan sin conexión', '앱처럼 열고 읽은 글은 오프라인에서도 볼 수 있습니다', 'アプリのように開き、読んだ記事はオフラインでも読めます'],
    '关注向阳乔木': ['', '關注向陽喬木', 'Follow Qiaomu', 'Qiaomu folgen', 'Suivre Qiaomu', 'Seguir a Qiaomu', 'Qiaomu 팔로우', 'Qiaomu をフォロー'],
    '微信公众号：向阳乔木推荐看': ['', '微信公眾號：向陽喬木推薦看', 'WeChat: Qiaomu Recommends', 'WeChat: Qiaomu empfiehlt', 'WeChat : Qiaomu recommande', 'WeChat: Qiaomu recomienda', '위챗: Qiaomu 추천', 'WeChat: Qiaomu おすすめ'],
    '回到首页': ['', '回到首頁', 'Back to home', 'Zur Startseite', "Retour à l'accueil", 'Volver al inicio', '홈으로', 'ホームへ'],
    '搜索视频': ['', '搜尋影片', 'Search videos', 'Videos suchen', 'Rechercher des vidéos', 'Buscar vídeos', '영상 검색', '動画を検索'],
    '最新精读': ['', '最新精讀', 'Latest deep-reads', 'Neueste Tiefenlesungen', 'Dernières lectures en chinois', 'Últimas lecturas en chino', '최신 정독', '最新の精読'],
    // ---- 首页 ----
    '搜索公司、产品、话题…': ['', '搜尋公司、產品、話題…', 'Search companies, products, topics…', 'Unternehmen, Produkte, Themen suchen…', 'Rechercher entreprises, produits, sujets…', 'Buscar empresas, productos, temas…', '기업·제품·주제 검색…', '企業・製品・話題を検索…'],
    '清除': ['', '清除', 'Clear', 'Löschen', 'Effacer', 'Borrar', '지우기', 'クリア'],
    '有文稿': ['', '有文稿', 'With transcript', 'Mit Transkript', 'Avec transcription', 'Con transcripción', '대본 있음', '文字起こしあり'],
    '看过的': ['', '看過的', 'Watched', 'Gesehen', 'Déjà vus', 'Vistos', '본 영상', '見たもの'],
    '最新': ['', '最新', 'Newest', 'Neueste', 'Plus récents', 'Más recientes', '최신순', '最新'],
    '随机一篇': ['', '隨機一篇', 'Random pick', 'Zufälliger Beitrag', 'Au hasard', 'Aleatorio', '무작위 하나', 'ランダムに読む'],
    '随机读一篇视频与文稿': ['', '隨機讀一篇影片與文稿', 'Open a random video with transcript', 'Zufälligen Beitrag mit Transkript öffnen', 'Ouvrir une vidéo aléatoire avec transcription', 'Abrir un vídeo aleatorio con transcripción', '대본이 있는 영상 무작위로 열기', '文字起こしのある動画をランダムに開く'],
    '最早': ['', '最早', 'Oldest', 'Älteste', 'Plus anciens', 'Más antiguos', '오래된순', '古い順'],
    '标题搜索': ['', '標題搜尋', 'Title search', 'Titelsuche', 'Recherche par titre', 'Búsqueda por título', '제목 검색', 'タイトル検索'],
    '筛选结果': ['', '篩選結果', 'Filtered results', 'Gefilterte Ergebnisse', 'Résultats filtrés', 'Resultados filtrados', '필터 결과', '絞り込み結果'],
    '从 1998 年开始': ['', '從 1998 年開始', 'From 1998', 'Ab 1998', 'Depuis 1998', 'Desde 1998', '1998년부터', '1998年から'],
    '最新在前': ['', '最新在前', 'Newest first', 'Neueste zuerst', 'Plus récents en premier', 'Más recientes primero', '최신순', '新しい順'],
    '再看 30 个': ['', '再看 30 個', 'Show 30 more', '30 weitere anzeigen', 'Afficher 30 de plus', 'Mostrar 30 más', '30개 더 보기', 'さらに30件表示'],
    '按年份浏览全部': ['', '按年份瀏覽全部', 'Browse all by year', 'Alle nach Jahr stöbern', 'Parcourir tout par année', 'Explorar todo por año', '연도별로 모두 보기', '年別にすべて見る'],
    '加载中…': ['', '載入中…', 'Loading…', 'Lädt…', 'Chargement…', 'Cargando…', '로딩 중…', '読み込み中…'],
    '没有找到': ['', '沒有找到', 'No results', 'Keine Ergebnisse', 'Aucun résultat', 'Sin resultados', '결과 없음', '見つかりません'],
    '符合条件的视频': ['', '符合條件的影片', 'matching videos', 'passende Videos', 'vidéos correspondantes', 'vídeos coincidentes', '일치하는 영상', '該当する動画'],
    '试试公司名、产品名或话题关键词，多个词用空格分开。': ['', '試試公司名、產品名或話題關鍵詞，多個詞用空格分開。', 'Try a company, product or topic keyword; separate words with spaces.', 'Probieren Sie ein Unternehmen, Produkt oder Thema; Wörter mit Leerzeichen trennen.', 'Essayez un nom d’entreprise, de produit ou un sujet ; séparez les mots par des espaces.', 'Prueba un nombre de empresa, producto o tema; separa las palabras con espacios.', '기업·제품·주제 키워드를 입력하세요. 여러 단어는 공백으로 구분.', '企業・製品・話題のキーワードを試してください。複数語は空白で区切ります。'],
    '在全部视频中搜索': ['', '在全部影片中搜尋', 'Search all videos', 'Alle Videos durchsuchen', 'Rechercher dans toutes les vidéos', 'Buscar en todos los vídeos', '모든 영상 검색', 'すべての動画を検索'],
    '阅读全文': ['', '閱讀全文', 'Read the full text', 'Ganzen Text lesen', 'Lire le texte intégral', 'Leer el texto completo', '전문 읽기', '全文を読む'],
    '继续阅读': ['', '繼續閱讀', 'Continue reading', 'Weiterlesen', 'Continuer à lire', 'Seguir leyendo', '이어서 읽기', '続きを読む'],
    '回到顶部': ['', '回到頂部', 'Back to top', 'Nach oben', 'Retour en haut', 'Volver arriba', '맨 위로', 'トップへ'],
    '个公开视频': ['', '個公開影片', 'public videos', 'öffentliche Videos', 'vidéos publiques', 'vídeos públicos', '개의 공개 영상', '件の公開動画'],
    '篇中文精读': ['', '篇中文精讀', 'Chinese deep-reads', 'chinesische Tiefenlesungen', 'lectures en chinois', 'lecturas en chino', '편의 중국어 정독', '篇の中国語精読'],
    '份英文文稿': ['', '份英文文稿', 'English transcripts', 'Englische Transkripte', 'transcriptions anglaises', 'transcripciones en inglés', '영문 대본', '英語の文字起こし'],
    '个英文词': ['', '個英文詞', 'English words', 'englische Wörter', 'mots anglais', 'palabras en inglés', '영어 단어', '英語の語数'],
    '文稿总字数': ['', '文稿總字數', 'Total transcript words', 'Gesamtwortzahl der Transkripte', 'Total des mots des transcriptions', 'Total de palabras de las transcripciones', '대본 총 단어 수', '文字起こし総語数'],
    '约 464 小时': ['', '約 464 小時', 'approx. 464 hours', 'ca. 464 Stunden', 'env. 464 heures', 'aprox. 464 horas', '약 464시간', '約464時間'],
    '覆盖 100% 的文稿': ['', '覆蓋 100% 的文稿', 'covers 100% of transcripts', 'deckt 100 % der Transkripte ab', 'couvre 100 % des transcriptions', 'cubre el 100 % de las transcripciones', '대본의 100%를 포함', '文字起こしの100%をカバー'],
    '与': ['', '與', 'matching', 'passend zu', 'correspondant à', 'coincidente con', '와 일치', 'と一致'],
    '相关': ['', '相關', '', '', '', '', '', ''],
    '份文稿里搜': ['', '份文稿裡搜', 'transcripts for', 'Transkripten nach', 'transcriptions pour', 'transcripciones para', '개 대본에서 검색', '件の文字起こしで検索'],
    '的原话': ['', '的原話', 'exact words', 'originalen Worten', 'paroles exactes', 'palabras exactas', '원문', 'の発言'],
    '全部': ['', '全部', 'All', 'Alle', 'Tous', 'Todos', '전체', 'すべて'],
    '已显示': ['', '已顯示', 'Showing', 'Angezeigt', 'Affichage', 'Mostrando', '표시 중', '表示中'],
    '中字': ['', '中字', 'Chinese subtitles', 'Chinesische Untertitel', 'Sous-titres chinois', 'Subtítulos chinos', '중국어 자막', '中国語字幕'],
    '看视频': ['', '看影片', 'Watch video', 'Video ansehen', 'Voir la vidéo', 'Ver vídeo', '영상 보기', '動画を見る'],
    '看视频 · B 站': ['', '看影片 · B 站', 'Watch video · Bilibili', 'Video ansehen · Bilibili', 'Voir la vidéo · Bilibili', 'Ver vídeo · Bilibili', '영상 보기 · Bilibili', '動画を見る · Bilibili'],
    // ---- 视频页 ----
    '英文文稿': ['', '英文文稿', 'English transcript', 'Englisches Transkript', 'Transcription anglaise', 'Transcripción en inglés', '영문 대본', '英語の文字起こし'],
    '金句': ['', '金句', 'Highlights', 'Zitate', 'Citations marquantes', 'Frases destacadas', '명구', '名言'],
    '档案': ['', '檔案', 'Archive entry', 'Archiv-Eintrag', 'Fiche d’archive', 'Entrada del archivo', '아카이브 항목', 'アーカイブ項目'],
    '相关视频': ['', '相關影片', 'Related video', 'Verwandtes Video', 'Vidéo associée', 'Vídeo relacionado', '관련 영상', '関連動画'],
    '上一个 / 下一个视频': ['', '上一個 / 下一個影片', 'Previous / next video', 'Vorheriges / nächstes Video', 'Vidéo précédente / suivante', 'Vídeo anterior / siguiente', '이전 / 다음 영상', '前の / 次の動画'],
    '精读目录': ['', '精讀目錄', 'Deep-read contents', 'Inhaltsverzeichnis', 'Sommaire de la lecture', 'Índice de la lectura', '정독 목차', '精読の目次'],
    '目录': ['', '目錄', 'Archive', 'Archiv', 'Archives', 'Archivo', '목록', 'アーカイブ'],
    '正文目录': ['', '正文目錄', 'Contents', 'Inhalt', 'Sommaire', 'Índice', '목차', '目次'],
    '阅读设置': ['', '閱讀設定', 'Reading settings', 'Lese-Einstellungen', 'Paramètres de lecture', 'Ajustes de lectura', '읽기 설정', '読書設定'],
    '恢复默认': ['', '恢復預設', 'Reset to default', 'Zurücksetzen', 'Réinitialiser', 'Restablecer', '기본값 복원', '既定に戻す'],
    '背景': ['', '背景', 'Background', 'Hintergrund', 'Arrière-plan', 'Fondo', '배경', '背景'],
    '字体': ['', '字體', 'Font', 'Schriftart', 'Police', 'Fuente', '글꼴', 'フォント'],
    '字号': ['', '字號', 'Text size', 'Schriftgröße', 'Taille du texte', 'Tamaño del texto', '글자 크기', '文字サイズ'],
    '行距': ['', '行距', 'Line height', 'Zeilenhöhe', 'Interligne', 'Interlineado', '줄 간격', '行間'],
    '版心宽度': ['', '版心寬度', 'Text width', 'Textbreite', 'Largeur du texte', 'Ancho del texto', '본문 폭', '本文幅'],
    '紧凑': ['', '緊湊', 'Compact', 'Kompakt', 'Compact', 'Compacto', '좁게', 'コンパクト'],
    '适中': ['', '適中', 'Medium', 'Mittel', 'Moyen', 'Medio', '보통', '標準'],
    '宽松': ['', '寬鬆', 'Relaxed', 'Weit', 'Large', 'Amplio', '넓게', 'ゆったり'],
    '窄': ['', '窄', 'Narrow', 'Schmal', 'Étroit', 'Estrecho', '좁게', '狭い'],
    '标准': ['', '標準', 'Standard', 'Standard', 'Standard', 'Estándar', '표준', '標準'],
    '宽': ['', '寬', 'Wide', 'Breit', 'Large', 'Ancho', '넓게', '広い'],
    '栏': ['', '欄', 'column', 'Spalten', 'colonnes', 'columnas', '열', '段'],
    '系统默认': ['', '系統預設', 'System default', 'Systemstandard', 'Par défaut', 'Predeterminado', '시스템 기본', 'システム既定'],
    '缩小字号': ['', '縮小字號', 'Smaller text', 'Kleiner', 'Réduire', 'Más pequeño', '글자 줄이기', '文字を小さく'],
    '放大字号': ['', '放大字號', 'Larger text', 'Größer', 'Agrandir', 'Más grande', '글자 키우기', '文字を大きく'],
    '浅色': ['', '淺色', 'Light', 'Hell', 'Clair', 'Claro', '라이트', 'ライト'],
    '护眼': ['', '護眼', 'Sepia', 'Sepia', 'Sépia', 'Sepia', '세피아', 'セピア'],
    '深色': ['', '深色', 'Dark', 'Dunkel', 'Sombre', 'Oscuro', '다크', 'ダーク'],
    '播放视频': ['', '播放影片', 'Play video', 'Video abspielen', 'Lire la vidéo', 'Reproducir vídeo', '영상 재생', '動画を再生'],
    '视频来源': ['', '影片來源', 'Video source', 'Videoquelle', 'Source vidéo', 'Fuente del vídeo', '영상 출처', '動画の出典'],
    'B 站版本为网友搬运，时间点可能差几秒': ['', 'B 站版本為網友搬運，時間點可能差幾秒', 'The Bilibili copy is re-uploaded by fans; timestamps may be off by seconds.', 'Die Bilibili-Version wurde von Fans hochgeladen; Zeitmarken können wenige Sekunden abweichen.', 'La version Bilibili est réuploadée par des fans ; les horodatages peuvent différer de quelques secondes.', 'La versión de Bilibili la subieron fans; las marcas de tiempo pueden ir unos segundos desfasadas.', 'B站 버전은 팬이 다시 올린 것으로 타임스탬프가 몇 초 어긋날 수 있습니다.', 'B版はファンによる再アップロードのため、タイムスタンプが数秒ずれる場合があります。'],
    '该视频暂无可播放源，可通过下方资源访问原始页面。': ['', '該影片暫無可播放來源，可透過下方資源存取原始頁面。', 'No playable source for this video yet; use the links below to reach the original page.', 'Für dieses Video gibt es noch keine abspielbare Quelle; nutzen Sie die Links unten zur Originalseite.', 'Aucune source lisible pour cette vidéo ; utilisez les liens ci-dessous pour accéder à la page originale.', 'Aún no hay fuente reproducible; usa los enlaces de abajo para ir a la página original.', '재생 가능한 소스가 없습니다. 아래 링크로 원본 페이지를 이용하세요.', '再生可能なソースがありません。下のリンクから元のページをご覧ください。'],
    '该视频的文稿与精读暂未收录，可直接观看视频。': ['', '該影片的文稿與精讀暫未收錄，可直接觀看影片。', 'Transcript and deep-read not yet available; you can watch the video directly.', 'Transkript und Tiefenlesung noch nicht verfügbar; Sie können das Video direkt ansehen.', 'Transcription et lecture en chinois pas encore disponibles ; vous pouvez regarder la vidéo.', 'Aún no hay transcripción ni lectura en chino; puedes ver el vídeo directamente.', '대본과 정독이 아직 없습니다. 영상을 바로 시청할 수 있습니다.', '文字起こしと精読はまだありません。動画を直接ご覧ください。'],
    '从现场发言里挑出的': ['', '從現場發言裡挑出的', 'Selected from the live remarks: ', 'Aus den live Äußerungen ausgewählt: ', 'Choisi parmi les propos en direct : ', 'Seleccionado de las declaraciones en vivo: ', '현장 발언에서 선별: ', '現場の発言から選んだ '],
    '句原话，附中文译文（AI 翻译，以英文原话为准）。点时间戳可跳到视频对应位置。': ['', '句原話，附中文譯文（AI 翻譯，以英文原話為準）。點時間戳可跳到影片對應位置。', 'quotes with Chinese translations (AI; the English original prevails). Click a timestamp to jump.', 'Zitate mit chinesischer Übersetzung (KI; englisches Original maßgeblich). Zeitstempel springen zum Video.', 'citations avec traduction chinoise (IA ; l’anglais fait foi). Cliquez sur un horodatage pour sauter.', 'citas con traducción al chino (IA; prevalece el original inglés). Haz clic en la marca de tiempo.', '개 인용문과 중국어 번역(AI, 원문 우선). 타임스탬프를 누르면 해당 지점으로 이동합니다.', '件の原文と中国語訳(AI、英語原文が優先)。タイムスタンプで該当箇所へ移動できます。'],
    '编辑精选的': ['', '編輯精選的', 'Editor’s picks: ', 'Redaktionelle Auswahl: ', 'Choix de la rédaction : ', 'Selección editorial: ', '편집자 선정: ', '編集部のおすすめ: '],
    '条现场发言，点时间戳可跳到视频对应位置。': ['', '條現場發言，點時間戳可跳到影片對應位置。', 'live remarks; click a timestamp to jump to that point in the video.', 'live Äußerungen; Zeitstempel springen zur entsprechenden Videostelle.', 'propos en direct ; cliquez sur un horodatage pour aller à ce moment de la vidéo.', 'declaraciones en vivo; haz clic en la marca de tiempo para saltar al vídeo.', '개의 현장 발언. 타임스탬프를 누르면 해당 지점으로 이동합니다.', '件の現場発言。タイムスタンプで該当箇所へ移動できます。'],
    '复制': ['', '複製', 'Copy', 'Kopieren', 'Copier', 'Copiar', '복사', 'コピー'],
    '生成海报': ['', '產生海報', 'Make poster', 'Poster erstellen', 'Créer une affiche', 'Crear póster', '포스터 만들기', 'ポスターを作成'],
    '说明': ['', '說明', 'Details', 'Details', 'Détails', 'Detalles', '설명', '説明'],
    '文稿来源：': ['', '文稿來源：', 'Transcript source: ', 'Transkriptquelle: ', 'Source de la transcription : ', 'Fuente de la transcripción: ', '대본 출처: ', '文字起こし出典: '],
    '已按语句合并成段落，并去掉 um、uh 等口头填充词。': ['', '已按語句合併成段落，並去掉 um、uh 等口頭填充詞。', 'Merged into paragraphs by sentence, with filler words like um and uh removed.', 'Zu Absätzen zusammengefasst, Füllwörter wie „um“ und „uh“ entfernt.', 'Regroupé en paragraphes ; les mots de remplissage comme « um » et « uh » ont été retirés.', 'Agrupado en párrafos; se eliminaron muletillas como «um» y «uh».', '문장별로 문단을 합치고 um, uh 같은 불필요한 말을 제거했습니다.', '文ごとに段落へまとめ、um や uh などの filler を除去しました。'],
    // ---- 阅读工具 / 搜索工具 ----
    '在本篇文稿中搜索…': ['', '在本篇文稿中搜尋…', 'Search in this transcript…', 'In diesem Transkript suchen…', 'Chercher dans cette transcription…', 'Buscar en esta transcripción…', '이 대본에서 검색…', 'この文字起こし内を検索…'],
    '在本篇文稿中搜索': ['', '在本篇文稿中搜尋', 'Search in this transcript', 'In diesem Transkript suchen', 'Chercher dans cette transcription', 'Buscar en esta transcripción', '이 대본에서 검색', 'この文字起こし内を検索'],
    '点击时间戳可跳到视频对应位置': ['', '點擊時間戳可跳到影片對應位置', 'Click a timestamp to jump to that point', 'Zeitstempel klicken, um zu springen', 'Cliquez sur un horodatage pour y sauter', 'Haz clic en la marca de tiempo para saltar', '타임스탬프를 눌러 해당 지점으로 이동', 'タイムスタンプで該当箇所へ移動'],
    '搜全部文稿 →': ['', '搜全部文稿 →', 'Search all transcripts →', 'Alle Transkripte durchsuchen →', 'Chercher toutes les transcriptions →', 'Buscar todas las transcripciones →', '모든 대본 검색 →', 'すべての文字起こしを検索 →'],
    '无匹配': ['', '無匹配', 'No matches', 'Keine Treffer', 'Aucun résultat', 'Sin coincidencias', '일치 없음', '一致なし'],
    '上一处': ['', '上一處', 'Previous', 'Vorherige', 'Précédent', 'Anterior', '이전', '前へ'],
    '下一处': ['', '下一處', 'Next', 'Nächste', 'Suivant', 'Siguiente', '다음', '次へ'],
    '关闭小窗': ['', '關閉小窗', 'Close mini player', 'Miniplayer schließen', 'Fermer le mini-lecteur', 'Cerrar mini reproductor', '미니 플레이어 닫기', 'ミニプレイヤーを閉じる'],
    '关闭': ['', '關閉', 'Close', 'Schließen', 'Fermer', 'Cerrar', '닫기', '閉じる'],
    '继续阅读': ['', '繼續閱讀', 'Continue reading', 'Weiterlesen', 'Continuer', 'Seguir leyendo', '이어서 읽기', '続きを読む'],
    '从': ['', '從', 'From ', 'Ab ', 'Depuis ', 'Desde ', '부터 ', 'から '],
    '开始播放': ['', '開始播放', 'playback', 'Wiedergabe', 'lecture', 'reproducción', '재생', '再生'],
    '播放': ['', '播放', 'Play', 'Abspielen', 'Lire', 'Reproducir', '재생', '再生'],
    '上次读到': ['', '上次讀到', 'Last read: ', 'Zuletzt gelesen: ', 'Dernière lecture : ', 'Última lectura: ', '마지막 읽음: ', '最後に読んだ場所: '],
    '已复制': ['', '已複製', 'Copied', 'Kopiert', 'Copié', 'Copiado', '복사됨', 'コピーしました'],
    '翻译这一段': ['', '翻譯這一段', 'Translate this paragraph', 'Diesen Absatz übersetzen', 'Traduire ce paragraphe', 'Traducir este párrafo', '이 문단 번역', 'この段落を翻訳'],
    '译': ['', '譯', 'Translate', 'Übersetzen', 'Traduire', 'Traducir', '번역', '訳'],
    '中文翻译 · 谷歌机翻': ['', '中文翻譯 · 谷歌機翻', 'Chinese translation · Google Translate', 'Chinesische Übersetzung · Google Übersetzer', 'Traduction chinoise · Google Traduction', 'Traducción al chino · Google Traductor', '중국어 번역 · 구글 번역', '中国語訳 · Google 翻訳'],
    '收起翻译': ['', '收起翻譯', 'Collapse translation', 'Übersetzung einklappen', 'Replier la traduction', 'Contraer traducción', '번역 접기', '翻訳を閉じる'],
    '翻译中…': ['', '翻譯中…', 'Translating…', 'Wird übersetzt…', 'Traduction…', 'Traduciendo…', '번역 중…', '翻訳中…'],
    '已复制译文与原文': ['', '已複製譯文與原文', 'Copied translation and original', 'Übersetzung und Original kopiert', 'Traduction et original copiés', 'Traducción y original copiados', '번역문과 원문을 복사했습니다', '訳文と原文をコピーしました'],
    '翻译服务暂时连不上，稍后再试。': ['', '翻譯服務暫時連不上，稍後再試。', 'Translation service unavailable; please try again later.', 'Übersetzungsdienst nicht erreichbar – bitte später erneut versuchen.', 'Service de traduction indisponible ; réessayez plus tard.', 'Servicio de traducción no disponible; inténtelo más tarde.', '번역 서비스에 연결할 수 없습니다. 나중에 다시 시도하세요.', '翻訳サービスに接続できません。しばらくしてからお試しください。'],
    '选中文字操作': ['', '選取文字操作', 'Selected-text actions', 'Aktionen für markierten Text', 'Actions sur le texte sélectionné', 'Acciones para el texto seleccionado', '선택한 텍스트 작업', '選択テキストの操作'],
    '已复制，带出处链接': ['', '已複製，附出處連結', 'Copied with source link', 'Mit Quelllink kopiert', 'Copié avec le lien source', 'Copiado con enlace de origen', '출처 링크와 함께 복사됨', '出典リンク付きでコピーしました'],
    '海报生成中…': ['', '海報產生中…', 'Generating poster…', 'Poster wird erstellt…', 'Génération de l’affiche…', 'Generando póster…', '포스터 생성 중…', 'ポスター作成中…'],
    '保存图片': ['', '儲存圖片', 'Save image', 'Bild speichern', "Enregistrer l'image", 'Guardar imagen', '이미지 저장', '画像を保存'],
    '复制图片': ['', '複製圖片', 'Copy image', 'Bild kopieren', "Copier l'image", 'Copiar imagen', '이미지 복사', '画像をコピー'],
    '手机上长按图片，可保存或直接发给朋友': ['', '手機上長按圖片，可儲存或直接傳給朋友', 'On mobile, long-press the image to save or share it.', 'Auf dem Handy lange auf das Bild drücken, um es zu speichern oder zu teilen.', 'Sur mobile, appuyez longuement sur l’image pour l’enregistrer ou la partager.', 'En móvil, mantén pulsada la imagen para guardarla o compartirla.', '모바일에서 이미지를 길게 눌러 저장하거나 공유하세요.', 'スマホでは画像を長押しして保存・共有できます。'],
    '分享海报': ['', '分享海報', 'Share poster', 'Poster teilen', "Partager l'affiche", 'Compartir póster', '포스터 공유', 'ポスターをシェア'],
    '图片已复制': ['', '圖片已複製', 'Image copied', 'Bild kopiert', 'Image copiée', 'Imagen copiada', '이미지 복사됨', '画像をコピーしました'],
    '复制失败，请用「保存图片」': ['', '複製失敗，請用「儲存圖片」', 'Copy failed — use “Save image”.', 'Kopieren fehlgeschlagen – „Bild speichern“ verwenden.', 'Échec de la copie – utilisez « Enregistrer l’image ».', 'Error al copiar: usa «Guardar imagen».', '복사 실패 — "이미지 저장"을 사용하세요.', 'コピーできませんでした。「画像を保存」を使ってください。'],
    '海报生成失败，请重试。': ['', '海報產生失敗，請重試。', 'Poster generation failed; please try again.', 'Poster konnte nicht erstellt werden – bitte erneut versuchen.', 'Échec de la génération de l’affiche ; réessayez.', 'No se pudo crear el póster; inténtelo de nuevo.', '포스터 생성에 실패했습니다. 다시 시도하세요.', 'ポスターを作成できませんでした。もう一度お試しください。'],
    // ---- 搜索页 ----
    '常被问到的': ['', '常被問到的', 'Frequently asked', 'Häufig gefragt', 'Questions fréquentes', 'Preguntas frecuentes', '자주 묻는 질문', 'よくある質問'],
    '这些词太常见，换个更具体的词试试。': ['', '這些詞太常見，換個更具體的詞試試。', 'These words are too common; try something more specific.', 'Diese Wörter sind zu häufig – versuchen Sie etwas Konkreteres.', 'Ces mots sont trop courants ; essayez quelque chose de plus précis.', 'Estas palabras son muy comunes; prueba algo más específico.', '이 단어는 너무 흔합니다. 더 구체적인 단어를 써보세요.', 'これらの語は一般的すぎます。より具体的な語をお試しください。'],
    '搜索中…': ['', '搜尋中…', 'Searching…', 'Suche läuft…', 'Recherche…', 'Buscando…', '검색 중…', '検索中…'],
    '翻译并搜索中…': ['', '翻譯並搜尋中…', 'Translating and searching…', 'Wird übersetzt und gesucht…', 'Traduction et recherche…', 'Traduciendo y buscando…', '번역하고 검색 중…', '翻訳して検索中…'],
    '谷歌翻译': ['', '谷歌翻譯', 'Google Translate', 'Google Übersetzer', 'Google Traduction', 'Google Traductor', '구글 번역', 'Google 翻訳'],
    '没翻译出来，只查精读': ['', '沒翻譯出來，只查精讀', 'Translation failed; searched deep-reads only', 'Übersetzung fehlgeschlagen – nur Tiefenlesungen durchsucht', 'Traduction échouée ; lectures en chinois seules', 'Falló la traducción; solo se buscaron las lecturas', '번역 실패 — 정독만 검색했습니다', '翻訳できず、精読のみ検索しました'],
    '或': ['', '或', 'or', 'oder', 'ou', 'o', '또는', 'または'],
    '检索词': ['', '檢索詞', 'Query', 'Suchbegriff', 'Requête', 'Consulta', '검색어', '検索語'],
    '搜索范围': ['', '搜尋範圍', 'Search scope', 'Suchbereich', 'Portée de recherche', 'Ámbito de búsqueda', '검색 범위', '検索範囲'],
    '英文原话': ['', '英文原話', 'English originals', 'Englische Originale', 'Originaux anglais', 'Originales en inglés', '영문 원문', '英語原文'],
    '这些词没法检索，换个说法试试。': ['', '這些詞沒辦法檢索，換個說法試試。', 'These terms cannot be searched; try rephrasing.', 'Diese Begriffe sind nicht durchsuchbar – versuchen Sie es anders.', 'Ces termes ne peuvent pas être recherchés ; reformulez.', 'Estos términos no se pueden buscar; prueba con otras palabras.', '이 단어는 검색할 수 없습니다. 다른 표현을 써보세요.', 'これらの語は検索できません。言い換えてお試しください。'],
    '索引加载失败，请检查网络后重试。': ['', '索引載入失敗，請檢查網路後重試。', 'Index failed to load; check your connection and retry.', 'Index konnte nicht geladen werden – Verbindung prüfen und erneut versuchen.', 'Échec du chargement de l’index ; vérifiez la connexion et réessayez.', 'No se pudo cargar el índice; revisa la conexión e inténtalo de nuevo.', '색인을 불러오지 못했습니다. 연결을 확인하고 다시 시도하세요.', 'インデックスを読み込めませんでした。接続を確認して再試行してください。'],
    '命中最多': ['', '命中最多', 'Most matches', 'Meiste Treffer', 'Le plus de résultats', 'Más coincidencias', '일치가 가장 많은순', '一致が最多'],
    '从早到晚': ['', '從早到晚', 'Oldest first', 'Älteste zuerst', 'Du plus ancien au plus récent', 'De más antiguo a más reciente', '오래된순', '古い順'],
    '从晚到早': ['', '從晚到早', 'Newest first', 'Neueste zuerst', 'Du plus récent au plus ancien', 'De más reciente a más antiguo', '최신순', '新しい順'],
    '篇精读': ['', '篇精讀', 'deep-reads', 'Tiefenlesungen', 'lectures en chinois', 'lecturas en chino', '편의 정독', '件の精読'],
    '个视频': ['', '個影片', 'videos', 'Videos', 'vidéos', 'vídeos', '개의 영상', '件の動画'],
    '换个说法，或去掉一些词': ['', '換個說法，或去掉一些詞', 'rephrase or remove some words', 'anders formulieren oder Wörter entfernen', 'reformulez ou retirez des mots', 'reformula o quita algunas palabras', '다른 표현을 쓰거나 단어를 줄여보세요', '言い換えるか語を減らしてみてください'],
    '精读是 AI 基于文稿写的中文导读，不是逐字翻译；点结果会定位到精读里的那一段。': ['', '精讀是 AI 基於文稿寫的中文導讀，不是逐字翻譯；點結果會定位到精讀裡的那一段。', 'Deep-reads are AI-written Chinese guides based on transcripts, not word-for-word translations; results jump to the relevant passage.', 'Tiefenlesungen sind KI-geschriebene chinesische Lesehilfen basierend auf Transkripten, keine Wort-für-Wort-Übersetzungen; Treffer springen zur Passage.', 'Les en chinois sont des guides rédigés par IA à partir des transcriptions, pas des traductions mot à mot ; les résultats mènent au passage.', 'Las lecturas en chino son guías escritas por IA a partir de las transcripciones, no traducciones palabra por palabra; los resultados llevan al pasaje.', '정독은 대본을 바탕으로 AI가 쓴 중국어 해설이며 직역이 아닙니다. 결과를 누르면 해당 문단으로 이동합니다.', '精読は文字起こしを基にAIが書いた中国語の解説で、逐語訳ではありません。結果を押すと該当箇所へ移動します。'],
    '按时间从早到晚排列，可以看他在这件事上的说法怎么变化。': ['', '按時間從早到晚排列，可以看他在這件事上的說法怎麼變化。', 'Sorted oldest first, so you can see how his view changed over time.', 'Älteste zuerst sortiert – so sehen Sie, wie sich seine Ansicht entwickelte.', 'Triés du plus ancien au plus récent : voyez comment son avis a évolué.', 'Ordenados de más antiguo a más reciente: verás cómo cambió su postura.', '오래된순으로 정렬되어 그의 견해 변화를 볼 수 있습니다.', '古い順に並んでいるため、見解の変化が分かります。'],
    '排序': ['', '排序', 'Sort', 'Sortieren', 'Trier', 'Ordenar', '정렬', '並べ替え'],
    '按年份分布': ['', '按年份分佈', 'By year', 'Nach Jahr', 'Par année', 'Por año', '연도별 분포', '年別'],
    '只看': ['', '只看', 'Only ', 'Nur ', 'Uniquement ', 'Solo ', '만 보기 ', 'のみ '],
    '看全部年份': ['', '看全部年份', 'All years', 'Alle Jahre', 'Toutes les années', 'Todos los años', '모든 연도', 'すべての年'],
    '加载失败': ['', '載入失敗', 'Load failed', 'Laden fehlgeschlagen', 'Échec du chargement', 'Error al cargar', '불러오기 실패', '読み込み失敗'],
    '无可查词': ['', '無可查詞', 'No searchable terms', 'Keine suchbaren Begriffe', 'Aucun terme recherchable', 'Sin términos que buscar', '검색할 수 있는 단어 없음', '検索できる語がありません'],
    '展开另外': ['', '展開另外', 'Show ', 'Weitere anzeigen ', 'Afficher ', 'Mostrar ', '더 보기 ', 'さらに表示 '],
    '处': ['', '處', 'matches', 'Treffer', 'résultats', 'coincidencias', '곳', '곳'],
    // ---- 通用 a11y / 提示 ----
    '跳到主要内容': ['', '跳到主要內容', 'Skip to main content', 'Zum Hauptinhalt springen', 'Aller au contenu principal', 'Saltar al contenido principal', '본문으로 건너뛰기', 'メインコンテンツへ'],
    '切换浅色 / 深色模式': ['', '切換淺色 / 深色模式', 'Switch light / dark mode', 'Helles / dunkles Design wechseln', 'Basculer le mode clair / sombre', 'Cambiar modo claro / oscuro', '라이트 / 다크 모드 전환', 'ライト / ダークモード切替'],
    '播放': ['', '播放', 'Play', 'Abspielen', 'Lire', 'Reproducir', '재생', '再生'],
    '关闭': ['', '關閉', 'Close', 'Schließen', 'Fermer', 'Cerrar', '닫기', '閉じる'],
    '已保存：断网后也能读这一页': ['', '已儲存：斷網後也能讀這一頁', 'Saved: this page works offline', 'Gespeichert: diese Seite funktioniert offline', 'Enregistré : cette page est disponible hors ligne', 'Guardado: esta página funciona sin conexión', '저장됨: 오프라인에서도 이 페이지를 읽을 수 있습니다', '保存しました: このページはオフラインでも読めます'],
    '有新版本可用': ['', '有新版本可用', 'A new version is available', 'Eine neue Version ist verfügbar', 'Une nouvelle version est disponible', 'Hay una nueva versión disponible', '새 버전이 있습니다', '新しいバージョンがあります'],
    '立即更新': ['', '立即更新', 'Update now', 'Jetzt aktualisieren', 'Mettre à jour', 'Actualizar ahora', '지금 업데이트', '今すぐ更新'],
    '已更新到最新版本': ['', '已更新到最新版本', 'Updated to the latest version', 'Auf die neueste Version aktualisiert', 'Mise à jour vers la dernière version', 'Actualizado a la última versión', '최신 버전으로 업데이트했습니다', '最新バージョンに更新しました'],
    '离线保存暂不可用，请刷新后重试': ['', '離線儲存暫不可用，請重新整理後重試', 'Offline save unavailable; refresh and retry', 'Offline-Speichern nicht verfügbar – aktualisieren und erneut versuchen', 'Enregistrement hors ligne indisponible ; rechargez et réessayez', 'Guardado sin conexión no disponible; actualiza e inténtalo de nuevo', '오프라인 저장을 사용할 수 없습니다. 새로고침 후 다시 시도하세요', 'オフライン保存を利用できません。更新して再試行してください'],
    '已安装到主屏幕 · 读过的文章可离线看': ['', '已安裝到主畫面 · 讀過的文章可離線看', 'Installed to Home Screen · read articles offline', 'Zum Home-Bildschirm hinzugefügt – Artikel offline lesen', 'Ajouté à l’écran d’accueil · articles lus hors ligne', 'Instalado en la pantalla de inicio · lee artículos sin conexión', '홈 화면에 설치됨 · 읽은 글은 오프라인에서도 볼 수 있습니다', 'ホーム画面に追加しました · 読んだ記事はオフラインでも読めます'],
    '点 Safari 底部的「分享」按钮': ['', '點 Safari 底部的「分享」按鈕', 'Tap the Share button at the bottom of Safari', 'Tippen Sie unten in Safari auf „Teilen“', 'Appuyez sur « Partager » en bas de Safari', 'Toca Compartir abajo en Safari', 'Safari 하단의 "공유" 버튼을 누르세요', 'Safari下部の「共有」ボタンをタップ'],
    '向下滑，选择「添加到主屏幕」': ['', '向下滑，選擇「新增至主畫面」', 'Scroll down and choose “Add to Home Screen”', 'Scrollen Sie nach unten und wählen Sie „Zum Home-Bildschirm hinzufügen“', 'Faites défiler et choisissez « Ajouter à l’écran d’accueil »', 'Desliza y elige «Añadir a la pantalla de inicio»', '아래로 스크롤해 "홈 화면에 추가"를 선택하세요', '下にスクロールして「ホーム画面に追加」を選択'],
    '点右上角「添加」': ['', '點右上角「新增」', 'Tap “Add” in the top-right', 'Tippen Sie oben rechts auf „Hinzufügen“', 'Appuyez sur « Ajouter » en haut à droite', 'Toca «Añadir» arriba a la derecha', '오른쪽 위 "추가"를 누르세요', '右上の「追加」をタップ'],
    // ---- 数据洞察页 chrome ----
    '数据洞察': ['', '數據洞察', 'Data insights', 'Daten-Einblicke', 'Aperçus des données', 'Análisis de datos', '데이터 인사이트', 'データ分析'],
    '把语料打包带走': ['', '把語料打包帶走', 'Take the corpus with you', 'Den Korpus mitnehmen', 'Emportez le corpus', 'Llévate el corpus', '말뭉치를 가져가세요', 'コーパスを持ち帰る'],
    '想让 AI 一口气读完整个档案？英文原始语料与本站的中文精读，各有各的下载方式。': ['', '想讓 AI 一口氣讀完整個檔案？英文原始語料與本站的中文精讀，各有各的下載方式。', 'Want an AI to read the whole archive at once? The English source corpus and this site’s Chinese deep-reads have separate downloads.', 'Soll eine KI das ganze Archiv auf einmal lesen? Der englische Originalkorpus und die chinesischen Tiefenlesungen haben eigene Downloads.', 'Un IA doit lire toutes les archives d’un coup ? Le corpus anglais original et les lectures en chinois ont chacun leur téléchargement.', '¿Quieres que una IA lea todo el archivo de una vez? El corpus original en inglés y las lecturas en chino tienen descargas distintas.', 'AI가 전체 아카이브를 한 번에 읽게 하고 싶으세요? 영어 원본 말뭉치와 중국어 정독은 각각 다른 방식으로 받을 수 있습니다.', 'AIにアーカイブ全体を一気に読ませたいですか。英語の原文コーパスと中国語の精読は、それぞれ別のダウンロード方法があります。'],
    '原始语料 · 来自 silicon-valley.tech': ['', '原始語料 · 來自 silicon-valley.tech', 'Source corpus · from silicon-valley.tech', 'Originalkorpus · von silicon-valley.tech', 'Corpus source · de silicon-valley.tech', 'Corpus original · de silicon-valley.tech', '원본 말뭉치 · silicon-valley.tech 제공', '原文コーパス · silicon-valley.tech 出典'],
    '英文原始语料': ['', '英文原始語料', 'English source corpus', 'Englischer Originalkorpus', 'Corpus anglais original', 'Corpus original en inglés', '영어 원본 말뭉치', '英語の原文コーパス'],
    '逐字文稿、X 帖子与回复、预言英文原文，都由档案方提供。本站不重复托管，只指过去——也请你在引用时注明原始出处。': ['', '逐字文稿、X 帖子與回覆、預言英文原文，都由檔案方提供。本站不重複託管，只指過去——也請你在引用時註明原始出處。', 'Verbatim transcripts, X posts and replies, and the original English predictions come from the archive. This site does not re-host them — we only link out. Please cite the original source.', 'Wortgetreue Transkripte, X-Posts und Antworten sowie die englischen Originalvorhersagen stammen vom Archiv. Diese Website hostet sie nicht erneut, sondern verlinkt nur. Bitte nennen Sie die Quelle.', 'Transcriptions mot pour mot, posts et réponses X et prédictions originales en anglais proviennent de l’archive. Ce site ne les réhéberge pas ; il renvoie simplement vers la source. Veuillez citer la source.', 'Las transcripciones literalmente, publicaciones y respuestas de X y las predicciones originales en inglés provienen del archivo. Este sitio no las vuelve a alojar; solo enlaza. Cita la fuente original.', '축자 대본, X 게시물·답글, 예측 영문 원문은 아카이브에서 제공합니다. 이 사이트는 다시 호스팅하지 않고 링크만 합니다. 출처를 밝혀 주세요.', '逐語の文字起こし、Xの投稿・返信、予測の英語原文はアーカイブ提供です。当サイトでは再 hosting せずリンクのみ。出典を明記してください。'],
    '数据下载页 ↗': ['', '資料下載頁 ↗', 'Data download page ↗', 'Datendownload-Seite ↗', 'Page de téléchargement ↗', 'Página de descarga ↗', '데이터 다운로드 ↗', 'データダウンロード ↗'],
    '全文单文件 ↗': ['', '全文單檔 ↗', 'Full text in one file ↗', 'Volltext in einer Datei ↗', 'Texte intégral en un fichier ↗', 'Texto completo en un archivo ↗', '전체 텍스트 단일 파일 ↗', '全文を1ファイルで ↗'],
    '版权归原权利方所有；请注明 Elon Musk Archive。': ['', '版權歸原權利方所有；請註明 Elon Musk Archive。', 'Copyright belongs to the rights holders; please credit Elon Musk Archive.', 'Urheberrecht liegt bei den Rechteinhabern; bitte Elon Musk Archive nennen.', 'Le droit d’auteur appartient aux titulaires ; veuillez citer Elon Musk Archive.', 'Los derechos pertenecen a sus titulares; cita Elon Musk Archive.', '저작권은 원 권리자에게 있습니다. Elon Musk Archive를 밝혀 주세요.', '著作権は権利者にあります。Elon Musk Archive を明記してください。'],
    '中文增量 · 本站独有': ['', '中文增量 · 本站獨有', 'Chinese increment · unique to this site', 'Chinesischer Mehrwert · nur hier', 'Apport chinois · exclusif à ce site', 'Aporte en chino · exclusivo de este sitio', '중국어 추가분 · 이 사이트만', '中国語の追加分 · 当サイト限定'],
    '中文精读语料包': ['', '中文精讀語料包', 'Chinese deep-read corpus pack', 'Paket chinesischer Tiefenlesungen', 'Pack de lectures en chinois', 'Paquete de lecturas en chino', '중국어 정독 말뭉치 팩', '中国語精読コーパスパック'],
    '篇 AI 中文精读，加上翻译整理后的预言、语录、主题与视频目录。按你的用法挑一个：': ['', '篇 AI 中文精讀，加上翻譯整理後的預言、語錄、主題與影片目錄。依你的用法挑一個：', 'AI Chinese deep-reads, plus translated predictions, quotes, themes and a video catalog. Pick the format you need:', 'KI-Tiefenlesungen auf Chinesisch, dazu übersetzte Vorhersagen, Zitate, Themen und ein Videoverzeichnis. Wählen Sie Ihr Format:', 'Lectures chinoises par IA, plus prédictions, citations, thèmes et catalogue vidéo traduits. Choisissez votre format :', 'Lecturas chinas por IA, más predicciones, citas, temas y un catálogo de vídeos traducidos. Elige el formato:', 'AI 중국어 정독과 번역·정리한 예측, 명언, 주제, 영상 목록입니다. 용도에 맞게 선택하세요:', 'AIによる中国語精読と、翻訳・整理した予測・名言・テーマ・動画一覧です。用途に合わせて選んでください:'],
    '全文单文件': ['', '全文單檔', 'Full text, one file', 'Volltext, eine Datei', 'Texte intégral, un fichier', 'Texto completo, un archivo', '전체 텍스트 단일 파일', '全文を1ファイルで'],
    '给 RAG / 长上下文': ['', '給 RAG / 長上下文', 'For RAG / long context', 'Für RAG / langen Kontext', 'Pour RAG / contexte long', 'Para RAG / contexto largo', 'RAG / 긴 컨텍스트용', 'RAG / ロングコンテキスト向け'],
    '完整语料包 ZIP': ['', '完整語料包 ZIP', 'Full corpus ZIP', 'Vollständiger Korpus-ZIP', 'ZIP du corpus complet', 'ZIP del corpus completo', '전체 말뭉치 ZIP', 'コーパス一式 ZIP'],
    '逐篇 Markdown + JSON': ['', '逐篇 Markdown + JSON', 'Per-article Markdown + JSON', 'Markdown pro Artikel + JSON', 'Markdown par article + JSON', 'Markdown por artículo + JSON', '글별 Markdown + JSON', '記事ごとの Markdown + JSON'],
    '文件清单': ['', '檔案清單', 'File list', 'Dateiliste', 'Liste des fichiers', 'Lista de archivos', '파일 목록', 'ファイル一覧'],
    '中文精读为 AI 改写、非官方翻译；引用请注明「elon.qiaomu.ai 中文精读」并链接网页版。': ['', '中文精讀為 AI 改寫、非官方翻譯；引用請註明「elon.qiaomu.ai 中文精讀」並連結網頁版。', 'Deep-reads are AI rewrites, not official translations; please cite “elon.qiaomu.ai deep-read” and link the web page.', 'Tiefenlesungen sind KI-Umschreibungen, keine offiziellen Übersetzungen; bitte „elon.qiaomu.ai Tiefenlesung“ nennen und verlinken.', 'Les lectures en chinois sont des réécritures par IA, pas des traductions officielles ; citez « elon.qiaomu.ai lecture en chinois » et liez la page.', 'Las lecturas en chino son reescrituras por IA, no traducciones oficiales; cita «elon.qiaomu.ai lectura en chino» y enlaza la página.', '정독은 AI가 다시 쓴 비공식 번역입니다. "elon.qiaomu.ai 정독"을 밝히고 웹 페이지를 링크해 주세요.', '精読はAIによる書き換えで公式翻訳ではありません。「elon.qiaomu.ai 精読」と明記し、ウェブページをリンクしてください。'],
    // ---- 预言 / 语录 / 主题 / 目录 / 免责 ----
    '预言与承诺追踪': ['', '預言與承諾追蹤', 'Promises & predictions', 'Versprechen & Vorhersagen', 'Promesses et prédictions', 'Promesas y predicciones', '약속 및 예측 추적', '約束と予測の追跡'],
    '马斯克时间': ['', '馬斯克時間', 'Elon time', 'Elon-Zeit', 'Elon time', 'Tiempo Elon', '일론 타임', 'イーロンタイム'],
    '逐条核实': ['', '逐條核實', 'Fact-checked one by one', 'Einzeln überprüft', 'Vérifié une par une', 'Verificado uno por uno', '항목별 확인', 'ひとつずつ確認'],
    '已兑现': ['', '已兌現', 'Kept', 'Erfüllt', 'Tenue', 'Cumplida', '이행됨', '実現'],
    '迟到兑现': ['', '遲到兌現', 'Kept, late', 'Verspätet erfüllt', 'Tenue mais tardive', 'Cumplida tarde', '늦게 이행', '遅れて実現'],
    '待验证': ['', '待驗證', 'Open', 'Offen', 'À vérifier', 'Pendiente', '확인 필요', '検証待ち'],
    '未兑现': ['', '未兌現', 'Missed', 'Nicht erfüllt', 'Non tenue', 'Incumplida', '미이행', '미실현'],
    '相关视频': ['', '相關影片', 'Related video', 'Verwandtes Video', 'Vidéo associée', 'Vídeo relacionado', '관련 영상', '関連動画'],
    '出处：': ['', '出處：', 'Source: ', 'Quelle: ', 'Source : ', 'Fuente: ', '출처: ', '出典: '],
    '原始来源': ['', '原始來源', 'Original source', 'Originalquelle', 'Source originale', 'Fuente original', '원본 출처', '元の出典'],
    '结果：': ['', '結果：', 'Result: ', 'Ergebnis: ', 'Résultat : ', 'Resultado: ', '결과: ', '結果: '],
    '说': ['', '說', 'said', 'sagte', 'a dit', 'dijo', '발언', '발언'],
    '期限': ['', '期限', 'Deadline', 'Frist', 'Échéance', 'Plazo', '기한', '期限'],
    '语录': ['', '語錄', 'Quotes', 'Zitate', 'Citations', 'Citas', '명언', '名言'],
    '按年份跳转': ['', '按年份跳轉', 'Jump by year', 'Nach Jahr springen', 'Aller à l’année', 'Ir por año', '연도별 이동', '年で移動'],
    '按年份': ['', '按年份', 'By year', 'Nach Jahr', 'Par année', 'Por año', '연도별', '年別'],
    '主题': ['', '主題', 'Themes', 'Themen', 'Thèmes', 'Temas', '주제', 'テーマ'],
    '按年份目录': ['', '按年份目錄', 'Browse by year', 'Nach Jahr stöbern', 'Parcourir par année', 'Explorar por año', '연도별 목록', '年別一覧'],
    '年': ['', '年', '', '', '', '', '년', '年'],
    '免责声明': ['', '免責聲明', 'Disclaimer', 'Haftungsausschluss', 'Avertissement', 'Aviso legal', '면책 조항', '免責事項'],
    // ---- 具体页面 kicker / 说明（选高频短句） ----
    '档案专题': ['', '檔案專題', 'Archive feature', 'Archiv-Spezial', 'Spécial archives', 'Especial del archivo', '아카이브 특집', 'アーカイブ特集'],
    '用数字看马斯克': ['', '用數字看馬斯克', 'Musk in numbers', 'Musk in Zahlen', 'Musk en chiffres', 'Musk en cifras', '숫자로 보는 머스크', '数字で見るマスク'],
    '马斯克在关心什么': ['', '馬斯克在關心什麼', 'What Musk cares about', 'Was Musk beschäftigt', 'Ce qui préoccupe Musk', 'Qué le importa a Musk', '머스크가 관심을 갖는 것', 'マスクが関心を持つこと'],
    '首页': ['', '首頁', 'Home', 'Startseite', 'Accueil', 'Inicio', '홈', 'ホーム'],
    '话题热力图': ['', '話題熱力圖', 'Topic heatmap', 'Themen-Heatmap', 'Carte de chaleur des sujets', 'Mapa de calor de temas', '주제 히트맵', '話題ヒートマップ'],
    '自己比一比': ['', '自己比一比', 'Compare for yourself', 'Selbst vergleichen', 'Comparez vous-même', 'Compara tú mismo', '직접 비교하기', '自分で比べる'],
    '比较': ['', '比較', 'Compare', 'Vergleichen', 'Comparer', 'Comparar', '비교', '比較'],
    '注意力分配：他在聊哪家公司': ['', '注意力分配：他在聊哪家公司', 'Attention share: which company he talks about', 'Aufmerksamkeitsanteil: über welche Firma er spricht', 'Part d’attention : quelle entreprise il évoque', 'Cuál empresa menciona más', '어느 기업을 가장 많이 언급하는가', 'どの会社について話すか'],
    '他嘴里的人': ['', '他嘴裡的人', 'People he mentions', 'Menschen, die er erwähnt', 'Les personnes qu’il mentionne', 'Las personas que menciona', '그가 언급하는 사람들', '彼が言及する人々'],
    '他嘴里的未来': ['', '他嘴裡的未來', 'The future he talks about', 'Die Zukunft, die er sieht', 'L’avenir dont il parle', 'El futuro del que habla', '그가 말하는 미래', '彼が語る未来'],
    '每年留下了多少公开视频': ['', '每年留下了多少公開影片', 'Public videos per year', 'Öffentliche Videos pro Jahr', 'Vidéos publiques par an', 'Vídeos públicos por año', '연도별 공개 영상 수', '年ごとの公開動画数'],
    '在什么场合说话': ['', '在什麼場合說話', 'Where he speaks', 'Wo er spricht', 'Où il parle', 'Dónde habla', '어디에서 말하는가', 'どこで話すか'],
    '最长的十场': ['', '最長的十場', 'The ten longest', 'Die zehn längsten', 'Les dix plus longues', 'Los diez más largos', '가장 긴 열 편', '最も長い10本'],
    '跟马斯克学英语：他最爱用的词': ['', '跟馬斯克學英語：他最愛用的詞', 'Learn English with Musk: his favourite words', 'Englisch mit Musk: seine Lieblingswörter', 'Apprendre l’anglais avec Musk : ses mots préférés', 'Aprende inglés con Musk: sus palabras favoritas', '머스크와 영어 배우기: 자주 쓰는 단어', 'マスクと英語を学ぶ：よく使う語'],
    '中文精读进度': ['', '中文精讀進度', 'Deep-read progress', 'Fortschritt der Tiefenlesungen', 'Progression des lectures en chinois', 'Progreso de las lecturas en chino', '정독 진행 상황', '精読の進捗'],
    '去读精读 →': ['', '去讀精讀 →', 'Read the deep-reads →', 'Zu den Tiefenlesungen →', 'Lire les lectures en chinois →', 'Leer las lecturas en chino →', '정독 읽기 →', '精読を読む →'],
    '视频': ['', '影片', 'Video', 'Video', 'Vidéo', 'Vídeo', '영상', '動画'],
    '对话': ['', '對話', 'Conversation', 'Gespräch', 'Conversation', 'Conversación', '대화', '対話'],
    '发布会': ['', '發布會', 'Keynote', 'Präsentation', 'Conférence', 'Presentación', '발표회', '発表会'],
    '演讲': ['', '演講', 'Talk', 'Rede', 'Discours', 'Discurso', '연설', 'スピーチ'],
    '股东会': ['', '股東會', 'Shareholder meeting', 'Hauptversammlung', 'Assemblée générale', 'Junta de accionistas', '주주총회', '株主総会'],
    '其他': ['', '其他', 'Other', 'Sonstige', 'Autre', 'Otro', '기타', 'その他'],
    '书籍': ['', '書籍', 'Books', 'Bücher', 'Livres', 'Libros', '책', '本'],
    '影视': ['', '影視', 'Film & TV', 'Film & TV', 'Cinéma & TV', 'Cine y TV', '영화·TV', '映画・TV'],
    '马斯克书单：他在访谈里提到的': ['', '馬斯克書單：他在訪談裡提到的', 'Musk’s reading list: the books he mentions: ', 'Musks Leseliste: die Bücher, die er erwähnt: ', 'La bibliothèque de Musk : les livres qu’il mentionne : ', 'La lista de lecturas de Musk: los libros que menciona: ', '머스크의 책 목록: 그가 언급한 책: ', 'マスクの読書リスト: 言及した本: '],
    '马斯克片单：他在访谈里聊过的': ['', '馬斯克片單：他在訪談裡聊過的', 'Musk’s watchlist: the films he talks about: ', 'Musks FilmListe: die Filme, über die er spricht: ', 'La filmographie de Musk : les films dont il parle : ', 'La lista de películas de Musk: las que comenta: ', '머스크의 영화 목록: 그가 이야기한 영화: ', 'マスクの映画リスト: 語った映画: '],
    '本书': ['', '本書', 'books', 'Bücher', 'livres', 'libros', '권', '冊'],
    '部电影和剧': ['', '部電影和劇', 'films and shows', 'Filme und Serien', 'films et séries', 'películas y series', '편의 영화와 드라마', '本の映画とドラマ']
  };

  var IDX = {};
  ORDER.forEach(function (l, i) { IDX[l] = i; });

  function t(key) {
    if (!DICT[key]) return key;
    var i = IDX[cur];
    var v = DICT[key][i];
    return v ? v : key;
  }

  function detectLang() {
    // URL 参数优先级最高：分享链接、CDN / 边缘规则注入的语言都能生效
    try {
      var m = new URLSearchParams(location.search).get('lang');
      if (m) {
        m = m.toLowerCase();
        if (IDX[m] !== undefined) return m;
        if (m.indexOf('zh-tw') === 0 || m.indexOf('zh-hk') === 0) return 'zh-TW';
        if (m.indexOf('zh') === 0) return 'zh';
        var base = m.split('-')[0];
        if (IDX[base] !== undefined) return base;
      }
    } catch (e) {}
    try {
      var saved = localStorage.getItem('em-lang');
      if (saved && IDX[saved] !== undefined) return saved;
    } catch (e) {}
    // 浏览器语言（自动识别）：比 IP 更尊重用户偏好，且无需后端
    var langs = navigator.languages || [navigator.language || 'zh-CN'];
    for (var k = 0; k < langs.length; k++) {
      var L = (langs[k] || '').toLowerCase();
      if (!L || L === 'en-us' && langs.length > 1) continue;
      if (L.indexOf('zh') === 0) {
        if (L.indexOf('hant') >= 0 || L.indexOf('tw') >= 0 || L.indexOf('hk') >= 0 || L.indexOf('mo') >= 0) return 'zh-TW';
        return 'zh';
      }
      var b = L.split('-')[0];
      if (IDX[b] !== undefined) return b;
    }
    return 'zh';
  }

  var cur = detectLang();

  // 只翻译文案：跳过内容容器与脚本/样式
  var SKIP = 'script,style,noscript,.ep-dek,.ins-note,.zh-article,.transcript-text,.quotes-list,.q-zh,.q-en,.qy-quote,.sr-snip,.sr-snip-zh,.sr-en,.ph-s,.ph-en,.ph-zh,.bk-body,.mv-body,.pr-claim,.pr-quote,.pr-outcome,.pr-src,.ep-title,.ep-title-en,.card-title,.card-title-en,.hero-title,.hero-en,.pick-title,.pick-en,.cont-title,.ar-t,.sr-hit,.sr-zh,.sr-interp,.sr-gt,.sr-unk,.zh-body,.tr-pop-t,.kit-tr-src,.kit-tr-out,[lang="en"]:not(html)';

  // 记录每个文本节点的简体原文，切换语言时从原文重新翻译（避免链式翻译）
  var ORIG = new WeakMap();
  function cacheOrig(root) {
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
    var n;
    while ((n = w.nextNode())) {
      if (!ORIG.has(n)) ORIG.set(n, n.nodeValue);
    }
  }

  // 把一句文案里出现的词典短语（长的优先）替换成目标语言，保留数字/专有名词。
  // single 关键字（如「或」「年」）不作子串替换，避免误伤内容里的字。
  // 整句精确命中优先；只有"动态拼装"的短文案才做子串替换。
  // 子串替换只用一组精心挑选的短语——它们不会出现在正文内容里，
  // 且本身是多字固定搭配，避免把「视频/数据」这种常用词误伤成半中半英。
  var SUB_KEYS = [
    '按年份浏览全部', '已显示', '篇精读', '个视频', '份文稿里搜',
    '份英文文稿', '个英文词', '文稿总字数', '约 464 小时', '覆盖 100% 的文稿',
    '条现场发言，点时间戳可跳到视频对应位置。',
    '句原话，附中文译文（AI 翻译，以英文原话为准）。点时间戳可跳到视频对应位置。',
    '篇 AI 中文精读，加上翻译整理后的预言、语录、主题与视频目录。按你的用法挑一个：',
    '全文单文件', '完整语料包 ZIP',
    '中文精读语料包', '逐篇 Markdown + JSON', '给 RAG / 长上下文', '文件清单',
    '在本篇文稿中搜索', '点击时间戳可跳到视频对应位置', '搜全部文稿 →',
    '马斯克书单：他在访谈里提到的', '马斯克片单：他在访谈里聊过的',
    '本书', '部电影和剧'
  ].sort(function (a, b) { return b.length - a.length; });

  function translateText(orig) {
    var i = IDX[cur];
    if (i === 0) return orig;
    // 1) 整句精确命中：直接返回整句译文
    var whole = orig.trim();
    if (DICT[whole]) {
      var wv = DICT[whole][i];
      if (wv) return orig.replace(whole, wv);
    }
    // 2) 短文案里的动态拼装：替换白名单短语
    var out = orig;
    for (var k = 0; k < SUB_KEYS.length; k++) {
      var key = SUB_KEYS[k];
      if (out.indexOf(key) < 0) continue;
      var entry = DICT[key];
      if (!entry) continue; // 白名单键必须在 DICT 中存在，避免异常中断整轮翻译
      var v = entry[i];
      if (!v) continue;
      out = out.split(key).join(v);
    }
    return out;
  }

  function translateFromOrig(root) {
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
    var n;
    while ((n = w.nextNode())) {
      var p = n.parentElement;
      if (!p || p.closest(SKIP)) continue;
      try {
        var orig = ORIG.has(n) ? ORIG.get(n) : n.nodeValue;
        if (!ORIG.has(n)) ORIG.set(n, orig);
        var next = translateText(orig);
        if (next !== n.nodeValue) n.nodeValue = next;
      } catch (e) {
        // 单个文本节点异常不应中断整轮翻译（更不应影响语言切换器）
      }
    }
    var els = [];
    if (root.nodeType === 1 && root.matches && root.matches('[aria-label],[title],[placeholder],[alt]')) els.push(root);
    if (root.querySelectorAll) {
      Array.prototype.push.apply(els, Array.prototype.slice.call(root.querySelectorAll('[aria-label],[title],[placeholder],[alt]')));
    }
    els.forEach(function (el) {
      if (el.closest(SKIP)) return;
      ['aria-label', 'title', 'placeholder', 'alt'].forEach(function (a) {
        var v = el.getAttribute(a);
        if (!v) return;
        var k = '__i18n_' + a;
        var orig = el.getAttribute(k);
        if (orig === null) { orig = v; el.setAttribute(k, orig); }
        var tr = translateText(orig);
        if (tr !== v) el.setAttribute(a, tr);
      });
    });
  }

  function setLang(lang) {
    if (IDX[lang] === undefined) lang = 'zh';
    cur = lang;
    try { localStorage.setItem('em-lang', lang); } catch (e) {}
    document.documentElement.setAttribute('lang', LANG_ATTR[lang] || 'zh-CN');
    cacheOrig(document.body);
    translateFromOrig(document.body);
    syncSwitcher();
    // 通知各 JS 模块用新语言重绘动态文案
    try { document.dispatchEvent(new CustomEvent('i18n:change', { detail: { lang: lang } })); } catch (e) {}
  }

  function syncSwitcher() {
    var btn = document.getElementById('i18nBtn');
    if (btn) btn.textContent = SHORT[cur] || '中';
    Array.prototype.forEach.call(document.querySelectorAll('[data-lang]'), function (el) {
      var on = el.getAttribute('data-lang') === cur;
      el.setAttribute('aria-current', on ? 'true' : 'false');
      el.classList.toggle('on', on);
    });
  }

  function buildSwitcher() {
    var host = document.querySelector('.header-actions') || document.querySelector('.mast-actions');
    if (!host || document.getElementById('i18nPicker')) return;
    var wrap = document.createElement('div');
    wrap.className = 'i18n-picker';
    wrap.id = 'i18nPicker';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'i18n-btn';
    btn.id = 'i18nBtn';
    btn.setAttribute('aria-label', 'Language / 语言');
    btn.setAttribute('aria-haspopup', 'true');
    btn.setAttribute('aria-expanded', 'false');
    btn.textContent = SHORT[cur] || '中';
    var menu = document.createElement('div');
    menu.className = 'i18n-menu';
    menu.setAttribute('role', 'menu');
    menu.hidden = true;
    ORDER.forEach(function (l) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('role', 'menuitem');
      b.setAttribute('data-lang', l);
      b.textContent = LABELS[l];
      b.addEventListener('click', function (e) {
        e.stopPropagation();
        setLang(l);
        menu.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
      });
      menu.appendChild(b);
    });
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      menu.hidden = !menu.hidden;
      btn.setAttribute('aria-expanded', menu.hidden ? 'false' : 'true');
    });
    document.addEventListener('click', function () { menu.hidden = true; btn.setAttribute('aria-expanded', 'false'); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { menu.hidden = true; btn.setAttribute('aria-expanded', 'false'); } });
    wrap.appendChild(btn);
    wrap.appendChild(menu);
    host.insertBefore(wrap, host.firstChild);
    syncSwitcher();
  }

  var observer = null, observing = false;
  function observe(root) {
    if (!('MutationObserver' in window)) return;
    if (!observer) {
      observer = new MutationObserver(function (records) {
        if (observing) return;
        observing = true;
        try {
          records.forEach(function (r) {
            r.addedNodes.forEach(function (n) {
              if (n.nodeType === 1) { cacheOrig(n); translateFromOrig(n); }
              else if (n.nodeType === 3) {
                var p = n.parentElement;
                if (p && !p.closest(SKIP)) {
                  var orig = n.nodeValue;
                  ORIG.set(n, orig);
                  var next = translateText(orig);
                  if (next !== orig) n.nodeValue = next;
                }
              }
            });
          });
        } finally { observing = false; }
      });
    }
    observer.observe(root, { childList: true, subtree: true });
  }

  function init() {
    document.documentElement.setAttribute('lang', LANG_ATTR[cur] || 'zh-CN');
    cacheOrig(document.body);
    if (cur !== 'zh') translateFromOrig(document.body);
    buildSwitcher();
    observe(document.body);
    // app.js / ep.js / search.js 动态渲染后重扫
    document.addEventListener('i18n:refresh', function () { translateFromOrig(document.body); });
  }

  window.I18N = {
    t: t,
    get lang() { return cur; },
    setLang: setLang,
    supported: ORDER.slice(),
    labels: LABELS,
    refresh: function () { try { translateFromOrig(document.body); } catch (e) {} }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
