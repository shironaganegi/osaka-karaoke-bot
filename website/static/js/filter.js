document.addEventListener('DOMContentLoaded', () => {
    console.log("🚀 Filter.js initialized");

    const searchInput = document.getElementById('store-search-input');
    const sortBtn = document.getElementById('sort-price-btn');
    const chainFilters = document.querySelectorAll('.filter-chain');
    const cardsContainer = document.querySelector('.store-list-container');

    if (!cardsContainer) {
        console.error("❌ Error: .store-list-container not found");
        return;
    }

    // NodeListを配列に変換
    let cards = Array.from(document.querySelectorAll('.store-card'));
    console.log(`🔍 Found ${cards.length} store cards`);

    // --- フィルタリング関数 ---
    const filterStores = () => {
        // 入力値を小文字化＆スペース除去
        const query = searchInput ? searchInput.value.toLowerCase().replace(/[\s　]+/g, '') : "";

        // チェックされたチェーンの値を取得
        const selectedChains = Array.from(chainFilters)
            .filter(cb => cb.checked)
            .map(cb => cb.value);

        console.log(`Filter: query="${query}", chains=[${selectedChains.join(',')}]`);

        cards.forEach(card => {
            // data-name属性（なければ空文字）を取得・正規化
            const name = (card.getAttribute('data-name') || "").toLowerCase().replace(/[\s　]+/g, '');
            const chain = card.getAttribute('data-chain');

            // 検索ワード判定
            // queryが空なら常にtrue、そうでなければnameに含まれるか
            const matchesSearch = !query || name.includes(query);

            // チェーン判定
            // 選択なしなら常にtrue、そうでなければchainが選択肢に含まれるか
            const matchesChain = selectedChains.length === 0 || selectedChains.includes(chain);

            if (matchesSearch && matchesChain) {
                card.style.display = ""; // 表示
            } else {
                card.style.display = "none"; // 非表示
            }
        });
    };

    // --- ソート関数 (安い順) ---
    const sortStores = () => {
        console.log("💰 Sorting by price...");

        // ソート実行
        cards.sort((a, b) => {
            const priceA = parseInt(a.getAttribute('data-price')) || 99999;
            const priceB = parseInt(b.getAttribute('data-price')) || 99999;
            return priceA - priceB;
        });

        // DOM再配置（appendChildで末尾に移動＝並び替え）
        cards.forEach(card => cardsContainer.appendChild(card));
        console.log("✅ Sort complete");
    };

    // イベントリスナー設定
    if (searchInput) {
        searchInput.addEventListener('input', filterStores);
    } else {
        console.warn("⚠️ Search input not found");
    }

    if (sortBtn) {
        sortBtn.addEventListener('click', (e) => {
            e.preventDefault();
            sortStores();
        });
    }

    if (chainFilters.length > 0) {
        chainFilters.forEach(cb => {
            cb.addEventListener('change', filterStores);
        });
    }
});
