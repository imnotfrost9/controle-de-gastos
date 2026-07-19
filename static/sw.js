// Este arquivo transforma o site em um app instalável
self.addEventListener('install', (e) => {
    console.log('[App] Instalado com sucesso');
});

self.addEventListener('fetch', (e) => {
    // Mantém o funcionamento normal buscando os dados da internet
});