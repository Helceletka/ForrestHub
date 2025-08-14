/**
 * ForrestHubLib - Knihovna pro komunikaci se serverem
 **/

class ForrestHubLib {
    // Definice možných stavů hry
    RUNNING = "running";
    PAUSED = "paused";
    STOPPED = "stopped";

    /**
     * Konstruktor knihovny
     * @param isGame {boolean} - zda se jedná o stránku hry
     * @param url {string} - URL serveru pro Socket.io (pokud není zadáno, použije se hostname + port)
     */
    constructor(isGame = true, url) {
        if (ForrestHubLib.instance) {
            return ForrestHubLib.instance;
        }

        // Nastavení projektu (podle URL cesty)
        this.project = decodeURIComponent(window.location.pathname.split('/')[1]);

        // Určení, jestli je stránka herní
        this.isGamePage = isGame;

        // Kontrola, zda je načten socket.io
        if (typeof io === 'undefined') {
            throw new Error('Socket.io není načteno.');
        }

        // Cesta pro Socket.IO (pokud je aplikace pod prefixem, např. /Udavač/, přidej ho)
        const firstSeg = window.location.pathname.split('/')[1] || '';
        const socketPath = firstSeg ? `/socket.io/${encodeURIComponent(firstSeg)}` : '/socket.io';

        // Vytvoření socketu bez pevného "http://", prohlížeč použije aktuální origin (vč. https)
        this.socket = url ? io(url, { path: socketPath }) : io({ path: socketPath });

        // Přidání základních event listenerů
        this.eventAddListener('connect', () => {
            this.logDebug('Připojeno k serveru!');
            // Získání stavu hry
            this.socketEmit('game_status_get', null);
            // Skrytí overlaye, pokud byl zobrazen
            this.uiHideOverlay();
        });

        this.eventAddListener('disconnect', () => {
            this.logDebug('Odpojeno od serveru.');
            this.uiShowOverlay(
                'Byl jsi odpojen od serveru. <br/>Hra nejspíš skončila nebo nastala neočekávaná chyba.',
                null,
                "danger",
                true
            );
        });

        this.eventAddListener('admin_messages', (message) => {
            // Zobrazení overlaye na 5 sekund
            this.uiShowOverlay(message, 5000, 'warning');
        });

        this.eventAddListener('game_status', (status) => {
            if (status === this.RUNNING) {
                this.uiHideOverlay();
                if (this.isGamePage) {
                    this.uiShowAlert('success', 'Hra spuštěna', 2000);
                }
            } else if (status === this.PAUSED) {
                this.uiShowOverlay('Hra je pozastavena', null, 'info');
            } else if (status === this.STOPPED) {
                this.uiShowOverlay('Hra byla ukončena', null, 'danger');
            } else {
                this.uiShowOverlay('Neznámý stav hry', null, 'warning');
            }
            this.uiUpdateGameStatus(status);
        });

        // Uložení instance do singletonu
        ForrestHubLib.instance = this;
    }

    /**
     * Získání instance, případně vytvoření nové
     * @param isGame {boolean}
     * @param url {string}
     * @returns {ForrestHubLib}
     */
    static getInstance(isGame = true, url) {
        if (!ForrestHubLib.instance) {
            ForrestHubLib.instance = new ForrestHubLib(isGame, url);
        }
        return ForrestHubLib.instance;
    }


    //////////////////////////////////////////////////
    //                   HERNÍ REŽIM                //
    //////////////////////////////////////////////////

    /**
     * Nastaví, jestli uživatel je (nebo není) na stránce hry
     * @param isGameMode {boolean} - true = stránka hry
     */
    gameSetMode(isGameMode) {
        this.isGamePage = isGameMode;
    }

    /**
     * Získání aktuálního stavu hry (async - čeká na odpověď)
     * @returns {Promise<string|null>}
     */
    async gameGetStatus() {
        try {
            const response = await this.socketEmitWithResponse("game_status_get", null);
            return response?.data || null;
        } catch (e) {
            console.error("Chyba při získávání stavu hry:", e);
            return null;
        }
    }

    //////////////////////////////////////////////////
    //                   NASTAVENÍ DB               //
    //////////////////////////////////////////////////

    /**
     * Změní používaný projekt (např. databázový kontext)
     * @param project {string} - název projektu
     */
    dbSetProject(project) {
        this.project = decodeURIComponent(project);
    }

    /**
     * Vnitřní metoda pro vyřešení názvu projektu (dekódování)
     * @param projectOverride {string|null}
     * @returns {string} - dekódovaný název
     */
    dbResolveProjectName(projectOverride = null) {
        return decodeURIComponent(projectOverride || this.project);
    }

    //////////////////////////////////////////////////
    //                 EVENTY / SOCKET              //
    //////////////////////////////////////////////////

    /**
     * Přidá listener pro konkrétní event
     * @param eventKey {string}
     * @param callback {function}
     */
    eventAddListener(eventKey, callback) {
        this.socket.on(eventKey, (data) => {
            callback(data);
        });
    }

    /**
     * Přidá více listenerů najednou
     * @param eventCallbacks {object} - { eventKey1: callback1, eventKey2: callback2, ... }
     */
    eventAddListeners(eventCallbacks) {
        Object.entries(eventCallbacks).forEach(([eventKey, callback]) => {
            this.socket.on(eventKey, callback);
        });
    }

    /**
     * Emituje event s daty a čeká na odpověď
     * @param event {string}
     * @param data {any}
     * @returns {Promise<unknown>}
     */
    socketEmitWithResponse(event, data) {
        return new Promise((resolve, reject) => {
            this.socketEmit(event, data, (response) => {
                if (response && response.status === 'ok') {
                    resolve(response);
                } else {
                    let message = `Chyba při zpracování události: ${event}`;
                    if (response && response.message) {
                        message = response.message;
                    }
                    console.error(message);
                    this.uiShowOverlay(message, null);
                    reject(new Error(message));
                }
            });
        });
    }

    /**
     * Emituje event s daty a volitelnou callback funkcí
     * @param event {string}
     * @param data {any|null}
     * @param callback {function|null}
     */
    socketEmit(event, data = null, callback = null) {
        if (callback) {
            this.socket.emit(event, data, callback);
        } else {
            this.socket.emit(event, data);
        }
    }

    /**
     * Odpojení od serveru ručně
     */
    socketDisconnect() {
        this.socket.disconnect();
        this.logDebug("Odpojeno od serveru ručně.");
    }

    /**
     * Změna serverové URL a vytvoření nového socketu
     * @param url {string} - nová adresa serveru
     */
    socketSetServerUrl(url) {
        this.logDebug(`Měním serverové URL na: ${url}`);
        this.socketDisconnect();

        const firstSeg = window.location.pathname.split('/')[1] || '';
        const socketPath = firstSeg ? `/socket.io/${encodeURIComponent(firstSeg)}` : '/socket.io';

        this.socket = url ? io(url, { path: socketPath }) : io({ path: socketPath });
        this.logDebug(`Připojeno k novému serveru: ${url}`);
    }

    //////////////////////////////////////////////////
    //                 DB OPERACE                   //
    //////////////////////////////////////////////////

    /**
     * Načte všechna data z databáze
     * @returns {Promise<object>}
     */
    async dbFetchAllData() {
        const db = await this.socketEmitWithResponse('db_get_all_data');
        return db?.data || {};
    }

    /**
     * Smaže všechna data z databáze
     * @returns {Promise<void>}
     */
    async dbClearAllData() {
        await this.socketEmitWithResponse('db_delete_all_data');
    }

    //////////////////////////////////////////////////
    //               DB: PROMĚNNÉ (VAR)             //
    //////////////////////////////////////////////////

    /**
     * Nastaví proměnnou v DB (key, value)
     * @param key {string}
     * @param value {any}
     * @param projectOverride {string|null}
     */
    async dbVarSetKey(key, value, projectOverride = null) {
        if (!key || typeof key !== "string") {
            throw new Error("dbVarSetKey: Key musí být neprázdný string.");
        }

        const project = this.dbResolveProjectName(projectOverride);
        await this.socketEmitWithResponse('var_key_set', { project, key, value });
    }

    /**
     * Získá hodnotu proměnné (key)
     * @param key {string}
     * @param projectOverride {string|null}
     * @returns {Promise<any>}
     */
    async dbVarGetKey(key, projectOverride = null) {
        if (!key || typeof key !== "string") {
            throw new Error("dbVarGetKey: Key musí být neprázdný string.");
        }

        const project = this.dbResolveProjectName(projectOverride);
        const response = await this.socketEmitWithResponse('var_key_get', { project, key, project });
        if (!response) {
            throw new Error(`dbVarGetKey: Neplatná odpověď od serveru pro key=${key}.`);
        }
        return response.data;
    }

    /**
     * Ověří, zda klíč existuje
     * @param key {string}
     * @param projectOverride {string|null}
     * @returns {Promise<boolean>}
     */
    async dbVarKeyExists(key, projectOverride = null) {
        if (!key || typeof key !== "string") {
            throw new Error("dbVarKeyExists: Key musí být neprázdný string.");
        }

        const project = this.dbResolveProjectName(projectOverride);
        const response = await this.socketEmitWithResponse('var_key_exist', { project, key });
        return !!response?.exists;
    }

    /**
     * Smaže klíč
     * @param key {string}
     * @param projectOverride {string|null}
     * @returns {Promise<void>}
     */
    async dbVarDeleteKey(key, projectOverride = null) {
        if (!key || typeof key !== "string") {
            throw new Error("dbVarDeleteKey: Key musí být neprázdný string.");
        }

        const project = this.dbResolveProjectName(projectOverride);
        await this.socketEmitWithResponse('var_key_delete', { project, key });
    }

    //////////////////////////////////////////////////
    //               DB: POLE (ARRAY)               //
    //////////////////////////////////////////////////

    /**
     * Přidá nový záznam do pole (DB). Každý záznam získá unikátní recordId.
     * @param arrayName {string}
     * @param value {any}
     * @param projectOverride {string|null}
     * @returns {Promise<void>}
     */
    async dbArrayAddRecord(arrayName, value, projectOverride = null) {
        if (!arrayName || typeof arrayName !== "string") {
            throw new Error("dbArrayAddRecord: arrayName musí být neprázdný string.");
        }

        const project = this.dbResolveProjectName(projectOverride);
        await this.socketEmitWithResponse('array_add_record', { project, arrayName, value });
    }

    /**
     * Smaže záznam z pole podle recordId
     * @param arrayName {string}
     * @param recordId {string}
     * @param projectOverride {string|null}
     * @returns {Promise<void>}
     */
    async dbArrayRemoveRecord(arrayName, recordId, projectOverride = null) {
        if (!arrayName || typeof arrayName !== "string") {
            throw new Error("dbArrayRemoveRecord: arrayName musí být neprázdný string.");
        }
        if (!recordId || typeof recordId !== "string") {
            throw new Error("dbArrayRemoveRecord: recordId musí být neprázdný string.");
        }

        const project = this.dbResolveProjectName(projectOverride);
        await this.socketEmitWithResponse('array_remove_record', { project, arrayName, recordId });
    }

    /**
     * Aktualizuje záznam v poli
     * @param arrayName {string}
     * @param recordId {string}
     * @param value {any}
     * @param projectOverride {string|null}
     * @returns {Promise<void>}
     */
    async dbArrayUpdateRecord(arrayName, recordId, value, projectOverride = null) {
        if (!arrayName || typeof arrayName !== "string") {
            throw new Error("dbArrayUpdateRecord: arrayName musí být neprázdný string.");
        }
        if (!recordId || typeof recordId !== "string") {
            throw new Error("dbArrayUpdateRecord: recordId musí být neprázdný string.");
        }

        const project = this.dbResolveProjectName(projectOverride);
        await this.socketEmitWithResponse('array_update_record', { project, arrayName, recordId, value });
    }

    /**
     * Získá všechny záznamy z pole podle názvu
     * @param arrayName {string}
     * @param projectOverride {string|null}
     * @returns {Promise<object>}
     */
    async dbArrayFetchAllRecords(arrayName, projectOverride = null) {
        if (!arrayName || typeof arrayName !== "string") {
            throw new Error("dbArrayFetchAllRecords: arrayName musí být neprázdný string.");
        }

        const project = this.dbResolveProjectName(projectOverride);
        const response = await this.socketEmitWithResponse('array_get_all_records', { project, arrayName });
        if (!response) {
            throw new Error("dbArrayFetchAllRecords: Neplatná odpověď od serveru.");
        }
        return response.data;
    }

    /**
     * Smaže všechny záznamy z daného pole
     * @param arrayName {string}
     * @param projectOverride {string|null}
     * @returns {Promise<void>}
     */
    async dbArrayClearRecords(arrayName, projectOverride = null) {
        if (!arrayName || typeof arrayName !== "string") {
            throw new Error("dbArrayClearRecords: arrayName musí být neprázdný string.");
        }

        const project = this.dbResolveProjectName(projectOverride);
        await this.socketEmitWithResponse('array_clear_records', { project, arrayName });
    }

    /**
     * Získá seznam všech projektů uložených v databázi
     * @returns {Promise<any>}
     */
    async dbArrayFetchProjects() {
        const response = await this.socketEmitWithResponse('array_list_projects', {});
        return response.data;
    }

    //////////////////////////////////////////////////
    //                   UI / ALERTY                //
    //////////////////////////////////////////////////

    /**
     * Aktualizuje UI prvky podle stavu hry
     * @param status {string}
     */
    uiUpdateGameStatus(status) {
        let statusText = "";
        switch (status) {
            case this.RUNNING:
                statusText = "Hra běží";
                break;
            case this.PAUSED:
                statusText = "Hra pozastavena";
                break;
            case this.STOPPED:
                statusText = "Hra ukončena";
                break;
            default:
                statusText = "?";
        }
        document.querySelectorAll(".game_status").forEach((element) => {
            element.innerText = statusText;
        });
    }

    /**
     * Zobrazí alert typu bootstrap na pár sekund
     * @param type {string} - např. 'success', 'warning', 'danger'
     * @param message {string} - zpráva
     * @param duration {number} - doba zobrazení v ms (výchozí 4000)
     */
    uiShowAlert(type, message, duration = 4000) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show shadow`;
        alertDiv.style.position = 'fixed';
        alertDiv.style.top = '10px';
        alertDiv.style.left = '10px';
        alertDiv.style.right = '10px';
        alertDiv.style.margin = '0 auto';
        alertDiv.style.maxWidth = '600px';
        alertDiv.style.zIndex = '9999';
        alertDiv.role = 'alert';
        alertDiv.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div>${message}</div>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;

        document.body.appendChild(alertDiv);
        setTimeout(() => alertDiv.remove(), duration);
    }

    /**
     * Zobrazí overlay (celoplošnou vrstvu) s textem a volitelným odpočtem
     * @param text {string} - zpráva, která se zobrazí
     * @param duration {number|null} - čas v ms, po kterém se overlay skryje
     * @param status {string} - styl overlaye (např. 'info', 'warning')
     * @param forceShow {boolean} - jestli se má ukázat i na ne-herní stránce
     */
    uiShowOverlay(text, duration = null, status = 'info', forceShow = false) {
        // Pokud nejde o herní stránku a není vynuceno zobrazení, zobrazíme jen alert
        if (!forceShow && !this.isGamePage) {
            this.logDebug('Overlay se nezobrazí, protože není herní stránka (pokud není forceShow).');
            this.uiShowAlert('info', `Zpráva: ${text}`, 5000);
            return;
        }

        let overlay = document.createElement('div');
        let message = document.createElement('div');
        let countdown = document.createElement('div');

        overlay.id = 'overlay';
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.backgroundColor = 'rgba(5,5,0,0.96)';
        overlay.style.zIndex = '9999';

        message.id = 'overlay-message';
        message.innerHTML = text;
        message.style.position = 'absolute';
        message.style.top = '30%';
        message.style.left = '50%';
        message.style.transform = 'translate(-50%, -50%)';
        message.style.color = 'white';
        message.style.fontFamily = 'sans-serif';
        message.style.fontSize = '32px';
        message.style.textAlign = 'center';

        countdown.style.position = 'absolute';
        countdown.style.top = '40%';
        countdown.style.left = '50%';
        countdown.style.transform = 'translate(-50%, -50%)';
        countdown.style.color = 'white';
        countdown.style.fontFamily = 'sans-serif';
        countdown.style.fontSize = '24px';
        countdown.style.textAlign = 'center';

        overlay.appendChild(message);
        overlay.appendChild(countdown);
        document.body.appendChild(overlay);

        // Pokud máme duration, zobrazíme odpočet
        if (duration) {
            let remainingTime = duration / 1000;
            countdown.innerText = `Zbývá ${remainingTime}s`;

            let countdownInterval = setInterval(() => {
                remainingTime -= 1;
                countdown.innerText = `Zbývá ${remainingTime}s`;

                if (remainingTime <= 0) {
                    clearInterval(countdownInterval);
                    this.uiHideOverlay();
                }
            }, 1000);
        }
    }

    /**
     * Skryje overlay, pokud je na obrazovce
     */
    uiHideOverlay() {
        let overlay = document.getElementById('overlay');
        if (overlay) {
            document.body.removeChild(overlay);
        }
    }

    /**
     * Vytvoří nový element s textem a zobrazí ho na obrazovce
     * @param message {string} - zpráva
     */
    logDebug(message) {
        console.log(`[ForrestHubLib] ${message}`);
    }
}
