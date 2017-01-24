# Kända problem
Installationen av httplib2 sätter fel rättigheter på `httplib2/cacerts.txt`
Detta resulterar i att när programmet körs så slängs ett fel när SSL
certifikaten ska laddas.

Felet åtgärdas genom att ändra rättigheterna på filerna så att alla i systemet kan läsa dem.

    chmod o+r -R  /usr/local/lib/python2.7/dist-packages/httplib2-0.9-py2.7.egg

På Mac OS X finns filerna på en annan plats

    chmod o+r -R /Library/Python/2.7/sitepackages/httplib2-0.9-py2.7.egg

Observera att versionsnummer kan behöva bytas ut i sökvägen.

Lösningen är hämtad från [StackOverflow](http://stackoverflow.com/questions/27870024/google-gmail-api-installed-app-shows-ioerror-13-from-module-ssl-py-w-o-sudo/29679378#29679378)

# Installera beroenden

## Pakethanterare

    pip install --upgrade google-api-python-client

## Manuellt
Ladda ned paket ifrån https://developers.google.com/api-client-library/python/start/installation

    tar zxf google-api-python-client-1.6.1.tar.gz
    cd google-api-python-client.1.6.1
    python setup.py install

# Skapa OAuth klientnyckel

1. Gå till https://console.developers.google.com/apis/dashboard
2. Se till att ha valt rätt projekt (sannolikt har du bara ett projekt ändå)
3. Aktivera API för Blogger genom att klicka på **ENABLE API** och leta upp Blogger
4. Gå till **Credentials** (i menyn i vänsterpanelen)
5. Klicka på **Create Credentials**
6. Skapa **OAuth client Id** för applikationstyp **Other**, ange namn "kommentarsbot" eller dylikt (valfritt)
7. Svara endast OK i dialogrutan som visas (vi laddar ned en konfigurationsfil med nyckeln senare)
8. Visa detaljer för den nya nyckeln genom att klicka på den i listan
9. Klicka **Download JSON**
10. Spara filen i denna katalogen och döp filen till `client_secrets.json`

# Konfigurera skriptet

Skapa en konfigurationsfil med namnet `config.json`.
Utgå antingen från exemplet nedan eller `config.example.json`.

    {
        "blogId": "http://example.blogspot.se",
        "hours": 10,
        "blacklist": ["123","456","789"],
        "contentBlacklist": ["http://propagandasite.com/", "banned term", "swearword"],
        "removalMethod": "markAsSpam"
    }

**blogId** kan vara antingen en URL eller det numeriska **blogId** för bloggen.
Det är rekommenderat att använda det numeriska värdet för att öka prestandan (minskar antal anrop med 1 per körning).

**hours** är ett numeriskt värde på hur gammal (i timmar) blog inlägg måste vara för att skannas efter kommentarer.

**blacklist** är en vektor med author id vars kommentarer ska rensas från blog poster.

**contentBlacklist** är en vektor med strängar/ord som är otillåtna i kommentarer.

**removalMethod** anger hur kommentarer ska tas bort. Värdet vara
antingen `delete`, `markAsSpam` eller `removeContent`.
Standardvärde är `markAsSpam`.
Observera dock att `removeContent` för närvarande inte fungerar
pga [vad som verkar ett fel hos Google](http://stackoverflow.com/questions/41732174/google-blogger-api-removecontent-returns-403-for-blog-administrator).

**lastRunOverlapMinutes** är antal minuter relativt innan senaste körningen som används till startdatum. Endast kommentarer skapade efter datumet hämtas.
Standardvärdet är 1.
Ifall inget startdatum skall användas (hämta alla kommentarer) sätts denna inställning till ett negativt värde, exempelvis -1.
Det är rekommenderat att använda minst 1 minuts överlappning för att undvika risken att kommentarer slinker igenom kontrollen.

# Hämta OAuth token
Programmet måste köras interaktivt för att hämta OAuth token, annars
kan inte den krypterade token skapas.

Token kommer sparas till filen `blogger.dat`.
För att tvinga ny autensiering så kan filen raderas.

Som standard kommer programmet skapa en tillfällig webbserver lokalt
och automatiskt öppna systemets standardwebbläsare för att ta emot
OAuth token från Google.

    python client.py

Detta är helt klart lättast att göra för att spara token.

Om du inte vill eller kan öppna webbläsaren automatiskt eller
starta lokal webbserver kör du programmet istället med

    python client.py  --noauth_local_webserver

# Blockera ny profil
Ett enklare skript finns för att lägga till en användare i **blacklist** i konfigurationsfilen.
Som parameter används antingen en URL eller endast det numeriska id:t.

    python blacklist.py https://www.blogger.com/profile/10000000000000000000

# Filer som programmet använder

`client.py` behöver ha åtkomsträttigheter att läsa och skriva till filerna `blogger.dat` och `client.state.json`.
Programmet försöker skapa filerna om de inte redan finns.

Läsrättigheter till filen `config.json` behövs också.
