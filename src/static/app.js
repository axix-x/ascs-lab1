// Second Brain Client Logic

document.addEventListener('DOMContentLoaded', () => {
    // State
    const state = {
        notes: [],
        categories: {},
        tags: {},
        activeCategory: 'all',
        activeTag: 'all',
        searchQuery: '',
        sortBy: 'updated',
        selectedNoteId: null,
        isEditing: false
    };

    // DOM Elements
    const categoryList = document.getElementById('categoryList');
    const tagCloud = document.getElementById('tagCloud');
    const notesList = document.getElementById('notesList');
    const notesCounter = document.getElementById('notesCounter');
    const activeFilterTitle = document.getElementById('activeFilterTitle');
    const searchInput = document.getElementById('searchInput');
    const clearSearch = document.getElementById('clearSearch');
    const sortSelect = document.getElementById('sortSelect');
    
    // Viewer elements
    const emptyViewer = document.getElementById('emptyViewer');
    const noteContent = document.getElementById('noteContent');
    const viewCategory = document.getElementById('viewCategory');
    const viewStatus = document.getElementById('viewStatus');
    const viewUpdated = document.getElementById('viewUpdated');
    const viewTitle = document.getElementById('viewTitle');
    const viewTags = document.getElementById('viewTags');
    const viewSource = document.getElementById('viewSource');
    const viewBody = document.getElementById('viewBody');
    const backlinksWrap = document.getElementById('backlinksWrap');
    const backlinksList = document.getElementById('backlinksList');
    const btnEdit = document.getElementById('btnEdit');
    const editorPane = document.getElementById('editorPane');
    const editContent = document.getElementById('editContent');
    const btnSaveEdit = document.getElementById('btnSaveEdit');
    const btnCancelEdit = document.getElementById('btnCancelEdit');

    // Modal elements
    const newNoteModal = document.getElementById('newNoteModal');
    const btnNewNote = document.getElementById('btnNewNote');
    const btnCloseModal = document.getElementById('btnCloseModal');
    const btnCancelModal = document.getElementById('btnCancelModal');
    const createNoteForm = document.getElementById('createNoteForm');

    // Init
    init();

    async function init() {
        await refreshAllData();
        setupEventListeners();
        // Automatically open the MOC note if available
        const moc = state.notes.find(n => n.tags.includes('moc') || n.title.includes('Карта'));
        if (moc) {
            openNote(moc.id);
        } else if (state.notes.length > 0) {
            openNote(state.notes[0].id);
        }
    }

    async function refreshAllData() {
        await Promise.all([loadNotes(), loadCategories(), loadTags()]);
        renderCategories();
        renderTags();
        renderNotesList();
    }

    async function loadNotes() {
        const params = new URLSearchParams();
        if (state.activeCategory !== 'all') params.append('category', state.activeCategory);
        if (state.activeTag !== 'all') params.append('tag', state.activeTag);
        if (state.searchQuery) params.append('q', state.searchQuery);

        const res = await fetch(`/api/notes?${params.toString()}`);
        state.notes = await res.json();
    }

    async function loadCategories() {
        const res = await fetch('/api/categories');
        state.categories = await res.json();
    }

    async function loadTags() {
        const res = await fetch('/api/tags');
        state.tags = await res.json();
    }

    function renderCategories() {
        let total = 0;
        for (const [cat, count] of Object.entries(state.categories)) {
            total += count;
            const badge = document.getElementById(`badge-${cat.toLowerCase()}`);
            if (badge) badge.textContent = count;
        }
        const badgeAll = document.getElementById('badge-all');
        if (badgeAll) badgeAll.textContent = total;
    }

    function renderTags() {
        tagCloud.innerHTML = '';
        
        // "All" tag
        const allTag = document.createElement('span');
        allTag.className = `tag-item ${state.activeTag === 'all' ? 'active' : ''}`;
        allTag.textContent = 'усі';
        allTag.addEventListener('click', () => {
            state.activeTag = 'all';
            refreshAllData();
        });
        tagCloud.appendChild(allTag);

        for (const [tag, count] of Object.entries(state.tags)) {
            const el = document.createElement('span');
            el.className = `tag-item ${state.activeTag === tag ? 'active' : ''}`;
            el.textContent = `#${tag} (${count})`;
            el.addEventListener('click', () => {
                state.activeTag = (state.activeTag === tag) ? 'all' : tag;
                refreshAllData();
            });
            tagCloud.appendChild(el);
        }
    }

    function renderNotesList() {
        notesList.innerHTML = '';

        // Sorting
        const sorted = [...state.notes].sort((a, b) => {
            if (state.sortBy === 'title') {
                return a.title.localeCompare(b.title);
            }
            return (b.updated || b.created).localeCompare(a.updated || a.created);
        });

        notesCounter.textContent = `Знайдено: ${sorted.length}`;
        activeFilterTitle.textContent = state.activeCategory === 'all' 
            ? (state.activeTag === 'all' ? 'Усі нотатки' : `Тег: #${state.activeTag}`)
            : `Категорія: ${state.activeCategory}`;

        if (sorted.length === 0) {
            notesList.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">🔍</span>
                    <h4>Нотаток не знайдено</h4>
                    <p>За вашим запитом "${state.searchQuery || state.activeTag}" немає збігів.</p>
                </div>
            `;
            return;
        }

        sorted.forEach(note => {
            const card = document.createElement('div');
            card.className = `note-card ${state.selectedNoteId === note.id ? 'active' : ''}`;
            
            const tagsHtml = note.tags.map(t => `<span class="tag-pill">#${t}</span>`).join('');
            
            card.innerHTML = `
                <div class="note-card-meta">
                    <span class="note-cat-badge cat-${note.category}">${note.category}</span>
                    <span class="note-card-date">${note.updated || note.created}</span>
                </div>
                <div class="note-card-title">${note.title}</div>
                <div class="note-card-snippet">${note.snippet}</div>
                <div class="note-card-tags">${tagsHtml}</div>
            `;

            card.addEventListener('click', () => {
                openNote(note.id);
            });

            notesList.appendChild(card);
        });
    }

    async function openNote(noteIdOrTitle) {
        state.isEditing = false;
        editorPane.style.display = 'none';
        viewBody.style.display = 'block';

        const res = await fetch(`/api/note?id=${encodeURIComponent(noteIdOrTitle)}`);
        if (!res.ok) {
            alert(`Нотатку "${noteIdOrTitle}" не знайдено.`);
            return;
        }

        const note = await res.json();
        state.selectedNoteId = note.id;

        // Update view
        emptyViewer.style.display = 'none';
        noteContent.style.display = 'block';

        viewCategory.textContent = note.category;
        viewCategory.className = `category-pill cat-${note.category}`;
        viewStatus.textContent = note.status;
        viewUpdated.textContent = `Оновлено: ${note.updated || note.created}`;
        viewTitle.textContent = note.title;
        viewSource.textContent = note.source || 'не вказано';

        // Tags
        viewTags.innerHTML = note.tags.map(t => `<span class="tag-pill">#${t}</span>`).join('');

        // Rendered Markdown HTML
        viewBody.innerHTML = note.body_html;

        // Attach event listeners to wikilinks
        viewBody.querySelectorAll('.wikilink').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const target = link.getAttribute('data-target');
                if (target) {
                    openNote(target);
                }
            });
        });

        // Backlinks
        if (note.backlinks && note.backlinks.length > 0) {
            backlinksWrap.style.display = 'block';
            backlinksList.innerHTML = '';
            note.backlinks.forEach(bl => {
                const item = document.createElement('div');
                item.className = 'backlink-item';
                item.innerHTML = `<span>🔗</span> <strong>${bl.title}</strong> <span class="tag-pill">${bl.category}</span>`;
                item.addEventListener('click', () => openNote(bl.id));
                backlinksList.appendChild(item);
            });
        } else {
            backlinksWrap.style.display = 'none';
        }

        // Setup editor initial value
        editContent.value = note.raw_content;

        // Re-render notes cards to highlight active
        document.querySelectorAll('.note-card').forEach(c => c.classList.remove('active'));
        const activeCard = Array.from(document.querySelectorAll('.note-card')).find(c => {
            return c.querySelector('.note-card-title').textContent === note.title;
        });
        if (activeCard) activeCard.classList.add('active');
    }

    function setupEventListeners() {
        // Category selection
        categoryList.querySelectorAll('li').forEach(li => {
            li.addEventListener('click', () => {
                categoryList.querySelectorAll('li').forEach(el => el.classList.remove('active'));
                li.classList.add('active');
                state.activeCategory = li.getAttribute('data-cat');
                refreshAllData();
            });
        });

        // Search
        let debounceTimer;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const val = e.target.value.trim();
            clearSearch.style.display = val ? 'block' : 'none';
            debounceTimer = setTimeout(() => {
                state.searchQuery = val;
                refreshAllData();
            }, 250);
        });

        clearSearch.addEventListener('click', () => {
            searchInput.value = '';
            clearSearch.style.display = 'none';
            state.searchQuery = '';
            refreshAllData();
        });

        // Sorting
        sortSelect.addEventListener('change', (e) => {
            state.sortBy = e.target.value;
            renderNotesList();
        });

        // Edit note toggling
        btnEdit.addEventListener('click', () => {
            state.isEditing = true;
            viewBody.style.display = 'none';
            editorPane.style.display = 'block';
        });

        btnCancelEdit.addEventListener('click', () => {
            state.isEditing = false;
            editorPane.style.display = 'none';
            viewBody.style.display = 'block';
        });

        btnSaveEdit.addEventListener('click', async () => {
            if (!state.selectedNoteId) return;
            const updatedContent = editContent.value;
            const res = await fetch('/api/note', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: state.selectedNoteId,
                    content: updatedContent
                })
            });
            if (res.ok) {
                await refreshAllData();
                await openNote(state.selectedNoteId);
            } else {
                alert('Помилка оновлення нотатки.');
            }
        });

        // Modal for New Note
        btnNewNote.addEventListener('click', () => {
            newNoteModal.classList.add('active');
            document.getElementById('mTitle').focus();
        });

        const closeModal = () => newNoteModal.classList.remove('active');
        btnCloseModal.addEventListener('click', closeModal);
        btnCancelModal.addEventListener('click', closeModal);

        createNoteForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const tags = document.getElementById('mTags').value
                .split(',')
                .map(t => t.trim())
                .filter(Boolean);

            const payload = {
                title: document.getElementById('mTitle').value.trim(),
                category: document.getElementById('mCategory').value,
                source: document.getElementById('mSource').value.trim() || 'власний конспект',
                tags: tags,
                content: document.getElementById('mContent').value.trim()
            };

            const res = await fetch('/api/notes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const newNote = await res.json();
                closeModal();
                createNoteForm.reset();
                await refreshAllData();
                if (newNote && newNote.id) {
                    openNote(newNote.id);
                }
            } else {
                alert('Помилка при створенні нотатки.');
            }
        });
    }
});
