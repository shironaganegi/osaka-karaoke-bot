document.addEventListener('DOMContentLoaded', function () {
    console.log("Filter.js loaded");

    const searchInput = document.getElementById('store-search-input');
    const sortBtn = document.getElementById('sort-price-btn');
    const chainFilters = document.querySelectorAll('.filter-chain');
    const container = document.querySelector('.store-list-container');

    if (!container) return;

    // 初期カードリストの取得 (NodeList -> Array)
    let cards = Array.from(container.getElementsByClassName('store-card'));

    // --- フィルタリング関数 ---
    function filterCards() {
        const query = searchInput.value.toLowerCase().replace(/\s+/g, '');
        const selectedChains = Array.from(chainFilters)
            .filter(cb => cb.checked)
            .map(cb => cb.value);

        cards.forEach(card => {
            const name = card.querySelector('.store-name').textContent.toLowerCase().replace(/\s+/g, '');
            const chain = card.getAttribute('data-chain');

            // 検索ワード判定
            const matchesSearch = name.includes(query);

            // チェーン判定 (チェックなし＝全表示、あり＝該当のみ)
            const matchesChain = selectedChains.length === 0 || selectedChains.includes(chain);

            if (matchesSearch && matchesChain) {
                card.style.display = ""; // flex/block等に戻す
            } else {
                card.style.display = "none";
            }
        });
    }

    // --- ソート関数 ---
    let sortAsc = true;
    function sortCards() {
        // 表示されているカードだけソートするか、全体をソートするか？
        // ここでは全体をソートして並べ替える

        cards.sort((a, b) => {
            let priceA = parseInt(a.getAttribute('data-price')) || 99999; // dataなしは後ろへ
            let priceB = parseInt(b.getAttribute('data-price')) || 99999;

            if (priceA === priceB) return 0;
            return sortAsc ? (priceA - priceB) : (priceB - priceA);
        });

        // DOM再配置
        cards.forEach(card => container.appendChild(card));

        // トグル
        // sortAsc = !sortAsc; // 今回は「安い順」固定ボタンっぽいのでトグルさせないか、させるか。
        // リクエスト「安い順に並び替える」 -> 押すたびにではなく、ワンショットで安い順にするだけでよいかも。
        // でもトグルできたほうが便利なのでトグルにするが、表記を変える
        // sortBtn.querySelector('span').textContent = sortAsc ? '💰' : '💹';
    }

    // イベントリスナー
    searchInput.addEventListener('input', filterCards);

    chainFilters.forEach(cb => {
        cb.addEventListener('change', filterCards);
    });

    sortBtn.addEventListener('click', (e) => {
        e.preventDefault();
        sortCards();
    });
});
