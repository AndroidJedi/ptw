import type { LegalDocument, LegalLanguage } from '../../../commander-web/src/landing/LegalLinks'

export type LegalSection = { title: string; paragraphs: string[] }
type Documents = Record<LegalLanguage, Record<LegalDocument, { intro: string; sections: LegalSection[] }>>

// Original reusable website baseline. Service-specific contracts must describe
// the actual offer; this text does not manufacture an operator or a transaction.
export const documents: Documents = {
  en: {
    terms: {
      intro: 'These terms describe use of Natal websites and how separate product or service terms fit alongside them. They do not, by themselves, create an order, subscription, reservation or payment obligation.',
      sections: [
        { title: 'Scope and the responsible business', paragraphs: [
          'Natal is a brand. The legal operator and contact details are identified below. A product supplied by a different business must identify that supplier and its responsibilities before you agree to an order.',
          'The terms of a particular offer must identify the service, seller, price, delivery or performance, eligibility and cancellation rules. Mandatory law takes priority. Agreed service terms govern that service; these website terms govern browsing. A privacy notice explains processing and is not a request for blanket consent.',
        ] },
        { title: 'Information, previews and forming a contract', paragraphs: [
          'Screens, examples and prototypes illustrate a proposed experience. Features, availability, suitability and results must be confirmed for the actual offer. Nothing in this clause excuses misleading advertising or removes responsibility for binding descriptions.',
          'Browsing, opening a contact link or sending an enquiry does not mean that you have purchased anything or accepted future paid terms. Before an order, you must receive the relevant terms in a form you can retain, have an opportunity to correct mistakes, and expressly agree to any payment obligation. A separate confirmation must explain when your order becomes binding.',
        ] },
        { title: 'Eligibility and permitted use', paragraphs: [
          'You must have the legal capacity and any authority required for an agreement you enter into. Age limits and any legally required parental consent must be stated for the particular service. These pages are not an invitation for children to send personal information.',
          'Do not use the website for unlawful activity, fraud, harassment, infringement, unauthorised access, malware or interference with others. Do not submit another person’s private information without authority. Reasonable security measures may restrict abusive traffic; they do not cancel consumer rights or paid entitlements.',
        ] },
        { title: 'Prices, payments and recurring services', paragraphs: [
          'Any paid offer must disclose the currency, total price, applicable taxes and unavoidable charges before commitment. Extra purchases require an express choice. These pages do not collect card details or process payments.',
          'A subscription must separately explain its billing interval, minimum term, renewal, trial conversion and accessible cancellation method before agreement. No recurring charge is authorised by visiting this website. Changes to an existing paid agreement require the notice, consent and termination rights required by law and that agreement.',
        ] },
        { title: 'Cancellation, withdrawal and refunds', paragraphs: [
          'A service’s cancellation policy must be available before purchase and cannot reduce statutory remedies. Where applicable, distance contracts may carry a 14-day withdrawal right; the starting point and exceptions depend on the contract and jurisdiction. Faulty or misdescribed supplies carry separate legal remedies.',
          'There is no universal “no refunds” rule. Immediate digital delivery or early service performance does not remove a withdrawal right merely because these terms say so: any lawful exception requires its own conditions and, where required, prior express consent and acknowledgement.',
          'For an existing order, contact the seller identified in its confirmation with the order reference and your request. You may use any other cancellation method allowed by applicable law. The seller must state the relevant deadlines, return procedure, costs and refund method in the service terms. Natal enquiries can use the contact below; do not send card numbers or identity documents with the initial request.',
        ] },
        { title: 'Our materials and your messages', paragraphs: [
          'Website text, designs, software, marks and images belong to their rights holders. You may view the site and retain information reasonably needed to consider or exercise your rights under an offer. Other use requires permission unless the law permits it.',
          'You retain rights in material you provide. Sending an enquiry permits its use to handle that enquiry, not public advertising or an unrestricted transfer of ownership. Do not send confidential material that is unnecessary to your request.',
        ] },
        { title: 'External services and specialised activities', paragraphs: [
          'Contact links and store buttons may take you to other services, including messaging platforms and app stores. Their own terms apply to their operations. An external link does not transfer or exclude any legal responsibility Natal has for its own service.',
          'Health, financial, legal, regulated, physical and marketplace services need their own eligibility, licensing, safety and supplier disclosures. A general website description is not personalised professional advice or an emergency service. These website terms do not authorise a regulated business to operate.',
        ] },
        { title: 'Availability and responsibility', paragraphs: [
          'Web access may be interrupted for maintenance, security or events outside reasonable control. We will act reasonably when correcting website errors. Rights relating to an agreed paid service remain governed by that agreement and mandatory law.',
          'Nothing here excludes liability for fraud, deliberate wrongdoing, death or personal injury caused by negligence where it cannot lawfully be excluded, or any other non-excludable liability. Consumer guarantees, rights to remedies and data-protection rights remain intact. These website terms impose no blanket liability cap, indemnity or waiver of collective or court remedies.',
        ] },
        { title: 'Complaints and applicable law', paragraphs: [
          'Send website complaints to the contact below. Include enough detail to investigate, without unnecessary sensitive data. You may also use a competent regulator, applicable dispute-resolution body or court without first giving up any statutory right.',
          'Applicable law and legally competent courts determine unresolved disputes. A future choice-of-law or forum clause in service terms must not deprive consumers of mandatory protections or courts available to them by law.',
        ] },
        { title: 'Changes and surviving rights', paragraphs: [
          'Each edition has a revision identifier and, once finalised, an effective date. New website terms operate prospectively. Publishing an update does not retrospectively rewrite an existing order or authorise new charges or data uses.',
          'Material changes to an ongoing service must follow its agreed and legally required notice and choice process. If a provision cannot lawfully apply, the remaining provisions apply only to the extent legally permissible. Both language versions are intended to express the same rights; mandatory interpretation rules prevail.',
        ] },
      ],
    },
    privacy: {
      intro: 'This notice covers Natal’s public information pages. A separate notice must explain any app, booking, payment or other service before it collects additional information. The operator responsible for these pages must be identified below.',
      sections: [
        { title: 'Information used by these pages', paragraphs: [
          'Page delivery exposes connection information, such as your IP address, request time and requested resource, to hosting and network providers. These public pages have no account, checkout or enquiry form. If you choose email, phone or an external messaging service, the recipient receives the information you send and relevant contact details.',
          'With your analytics choice enabled, we receive page-view and contact-click events, a random in-memory visit identifier, event identifiers, the page/version, a broad screen-size class and an advertising attribution reference if present. The application event payload does not include your name, email, full referrer, IP address or precise location. Network services still see connection data; random identifiers are not a promise of anonymity.',
        ] },
        { title: 'Purposes and legal grounds', paragraphs: [
          'Page delivery and proportionate security serve the legitimate interest of making the site available and protecting it, where that ground is available and does not override your rights. Responding to a requested pre-contract enquiry may be necessary for steps you request toward a contract; other correspondence serves the legitimate interest of answering you. Legal obligations may require particular records.',
          'Optional audience measurement and Meta advertising measurement are separate consent choices. Refusing them does not prevent access to the page. Consent to tracking is not consent to email marketing, payment, new services or sensitive-data processing.',
        ] },
        { title: 'Meta and other recipients', paragraphs: [
          'If you allow marketing measurement, Meta Pixel receives page-view and browser/connection information and may read or set identifiers and associate activity with a Meta account. Meta may use data for advertising measurement and its own purposes under its privacy policy. Marketing measurement is off until you allow it.',
          'Google Firebase Hosting delivers the public shell; the Natal application host receives page and permitted measurement requests. Authorised support and technical providers may process information needed for their tasks. Email, phone, messaging and store providers receive information when you choose their services. Authorities or advisers may receive information when legally required or necessary for a specific lawful claim. The operator must confirm its provider arrangements and any international transfers before this notice is final.',
        ] },
        { title: 'Retention and international transfers', paragraphs: [
          'The Cookie policy explains browser preference storage. Correspondence, security logs, individual measurement events, backups and aggregate reports require separate retention periods or clear deletion criteria. The operator’s confirmed schedule and transfer arrangements appear below; an empty disclosure means this draft is incomplete, not that data are immediately deleted or never leave your country.',
          'Where data-protection law requires a transfer safeguard, the operator must identify the countries or destinations and applicable mechanism, and explain how to obtain a copy. Accepting optional tracking alone is not a substitute for those safeguards.',
        ] },
        { title: 'Your choices and rights', paragraphs: [
          'Use Cookie settings on any page to change or withdraw optional consent. Withdrawal stops future optional collection on this browser; it does not reverse processing that already lawfully occurred. To request access, correction, deletion, restriction or a portable copy where applicable, use the contact below. Rights and lawful exceptions depend on your jurisdiction and the processing involved.',
          'Right to object: you can object to processing based on legitimate interests for reasons relating to your situation, and to direct marketing at any time. We may request proportionate information to confirm identity; an initial request does not require a passport. Requests are handled within the applicable legal period, with explanations of any lawful extension or refusal.',
        ] },
        { title: 'Complaints', paragraphs: [
          'You can complain to the relevant data-protection authority, including the Ukrainian Parliament Commissioner for Human Rights in Ukraine, an EEA supervisory authority where available, or the Information Commissioner’s Office in the UK. Contacting us first is optional and does not remove your right to complain.',
        ] },
        { title: 'Children, sensitive information and automated decisions', paragraphs: [
          'These information pages do not request children’s data, health information, payment-card data or other sensitive information. Do not send such information in an ordinary enquiry. A future service needing it must provide a specific notice and a valid legal basis before collection.',
          'These pages do not make automated decisions that grant or deny you a service or have similarly significant effects. Generated illustrations and interface demonstrations are website content, not decisions about you. New profiling or decision systems require a separate explanation and applicable safeguards.',
        ] },
        { title: 'Updates and contact', paragraphs: [
          'The revision below identifies this notice. Material processing changes require an updated notice before the new activity and fresh consent when needed. An update cannot silently broaden an earlier consent. Use the contact below for website privacy questions, quoting the page or service concerned.',
        ] },
      ],
    },
    cookies: {
      intro: 'Cookies and similar browser storage can remember preferences or recognise a browser. Optional audience and advertising measurement are disabled until you choose them. You can read the site and these policies without allowing either.',
      sections: [
        { title: 'Your preference record', paragraphs: [
          'After a choice, this site stores natal_privacy_preferences_v2 in local storage on this browser. It records the notice version, your separate analytics and marketing choices and the time of the decision. We honour it for up to 180 days, then ask again. Browser settings can remove it sooner. Local storage does not delete itself on a timer, so an expired record may remain on your device until overwritten or cleared; it no longer authorises tracking.',
          'This preference record is used to respect your choice, not to advertise. If browser storage is blocked, your choice applies for the current page session and we may ask again on a later visit. The older Meta-only preference is not treated as consent to this notice.',
        ] },
        { title: 'Optional audience measurement', paragraphs: [
          'Analytics permission enables Natal’s first-party page and contact-click measurement. The visit identifier exists only in page memory and is regenerated on reload; no analytics identifier is written to a cookie or local storage. Server records may remain after the page closes, as explained in the Privacy policy. Cookie-free does not mean that data-protection rules do not apply.',
        ] },
        { title: 'Optional advertising measurement', paragraphs: [
          'Marketing permission enables Meta Pixel for page-view measurement. It may use cookies such as _fbp and _fbc and information about your browser, page URL and connection. Meta determines some identifiers and their lifetimes; these may vary with browser and account settings. Consult Meta’s cookie and privacy policies linked below for its current practices.',
          'Allowing audience measurement does not allow Meta. We do not load its library or send Pixel events before marketing permission. External services you deliberately visit, such as a messaging platform or app store, manage their own consent separately.',
        ] },
        { title: 'Changing or withdrawing your choice', paragraphs: [
          'Open Cookie settings, adjust the two choices and save, or select Reject optional to turn both off. Rejecting is available on the first panel alongside Allow all. We stop new optional events, revoke Pixel consent and remove accessible first-party _fbp and _fbc cookies when marketing permission is withdrawn.',
          'We cannot erase cookies on Meta’s own domains or retrieve information already sent. Use your browser or Meta account controls for those records, and contact the relevant controller to exercise data rights. Choices apply to this browser and origin; another device or cleared storage may require another choice.',
        ] },
        { title: 'Policy changes', paragraphs: [
          'New optional vendors or purposes require a notice and consent update before activation. Simply publishing a revised policy does not permit additional tracking. This document covers the public Natal website, not all storage used by a future app.',
        ] },
      ],
    },
  },
  uk: {
    terms: {
      intro: 'Ці умови описують користування сайтами Natal та їхній зв’язок з окремими умовами продуктів і послуг. Самі по собі вони не створюють замовлення, підписки, бронювання чи обов’язку сплатити кошти.',
      sections: [
        { title: 'Сфера дії та відповідальний суб’єкт', paragraphs: [
          'Natal — це бренд. Нижче мають бути зазначені юридичний оператор і його контакти. Якщо продукт надає інший суб’єкт, його особу та обов’язки потрібно розкрити до погодження замовлення.',
          'Умови конкретної пропозиції мають визначати послугу, продавця, ціну, доставку чи виконання, вимоги до користувача та скасування. Імперативні норми закону мають пріоритет. Погоджені умови послуги регулюють цю послугу, а ці умови — користування сайтом. Політика конфіденційності пояснює обробку даних і не є запитом на необмежену згоду.',
        ] },
        { title: 'Інформація, демонстрації та укладення договору', paragraphs: [
          'Екрани, приклади й прототипи ілюструють запропонований досвід. Функції, доступність, придатність і результати потрібно підтвердити для конкретної пропозиції. Це положення не виправдовує оманливу рекламу та не скасовує відповідальність за обов’язкові описи.',
          'Перегляд сайту, перехід до контакту або звернення не означають купівлю чи прийняття майбутніх платних умов. До замовлення користувач має отримати відповідні умови у формі, яку можна зберегти, можливість виправити помилки та явно погодитися з обов’язком оплати. Окреме підтвердження має пояснювати момент укладення договору.',
        ] },
        { title: 'Правоздатність і належне використання', paragraphs: [
          'Для укладення договору необхідні відповідна дієздатність і повноваження. Вікові обмеження та необхідна за законом згода батьків визначаються для конкретної послуги. Ці сторінки не запрошують дітей надсилати персональні дані.',
          'Заборонені незаконна діяльність, шахрайство, переслідування, порушення чужих прав, несанкціонований доступ, шкідливе ПЗ та перешкоджання іншим. Не надсилайте чужі приватні дані без повноважень. Розумні заходи безпеки можуть обмежувати зловживання, але не скасовують прав споживача чи оплачених зобов’язань.',
        ] },
        { title: 'Ціни, оплата та підписки', paragraphs: [
          'До прийняття платної пропозиції мають бути розкриті валюта, повна ціна, податки та неминучі платежі. Додаткові покупки потребують окремого вибору. Ці сторінки не збирають реквізитів карток і не приймають платежів.',
          'Умови підписки мають заздалегідь визначати період оплати, мінімальний строк, поновлення, перехід із пробного періоду та доступний спосіб скасування. Відвідування сайту не дозволяє регулярних списань. Зміни чинного платного договору потребують повідомлення, згоди та права припинення у випадках, передбачених законом і договором.',
        ] },
        { title: 'Скасування, відмова та повернення коштів', paragraphs: [
          'Політика скасування конкретної послуги має бути доступна до покупки й не може звужувати законні засоби захисту. Коли це застосовно, дистанційний договір може передбачати 14-денне право відмови; початок строку й винятки залежать від договору та юрисдикції. Недоліки чи невідповідність опису дають окремі права.',
          'Універсального правила «кошти не повертаються» немає. Негайне надання цифрового вмісту чи ранній початок послуги не скасовують право відмови лише через текст цих умов: законний виняток потребує виконання власних вимог, зокрема попередньої явної згоди й підтвердження, якщо вони обов’язкові.',
          'Щодо чинного замовлення зверніться до продавця з підтвердження замовлення, вказавши його номер і свій запит. Ви також можете використати інший дозволений законом спосіб скасування. Продавець має зазначити строки, порядок повернення, витрати та спосіб відшкодування в умовах послуги. Для звернень до Natal використовуйте контакт нижче; не додавайте до першого запиту номер картки чи документи особи.',
        ] },
        { title: 'Матеріали сайту та ваші повідомлення', paragraphs: [
          'Тексти, дизайн, програмне забезпечення, позначення й зображення належать їхнім правовласникам. Ви можете переглядати сайт і зберігати інформацію, розумно необхідну для оцінки пропозиції чи захисту своїх прав. Інше використання потребує дозволу, якщо закон не передбачає винятку.',
          'Права на надані вами матеріали залишаються у вас. Надсилання звернення дозволяє використати його для відповіді, а не для публічної реклами чи необмеженого відчуження прав. Не надсилайте конфіденційних відомостей, непотрібних для запиту.',
        ] },
        { title: 'Зовнішні сервіси та спеціалізована діяльність', paragraphs: [
          'Контактні посилання та кнопки магазинів можуть відкривати сторонні сервіси, зокрема месенджери й магазини застосунків. Їхню діяльність регулюють власні умови. Зовнішнє посилання не передає й не виключає законної відповідальності Natal за власну послугу.',
          'Медичні, фінансові, юридичні, регульовані, фізичні та посередницькі послуги потребують власних вимог до користувачів, ліцензій, правил безпеки та відомостей про виконавця. Загальний опис на сайті не є персональною професійною порадою чи екстреною допомогою. Ці умови не дозволяють здійснювати регульовану діяльність.',
        ] },
        { title: 'Доступність і відповідальність', paragraphs: [
          'Доступ може перериватися через обслуговування, безпеку чи обставини поза розумним контролем. Помилки сайту мають виправлятися розумно. Права за погодженою платною послугою визначаються її договором та обов’язковими нормами закону.',
          'Ці умови не виключають відповідальності за шахрайство, умисні дії, смерть чи шкоду здоров’ю через недбалість, коли таке виключення заборонене, та іншої відповідальності, яку не можна виключити. Гарантії споживача, засоби захисту та права на захист даних зберігаються. Тут немає загального ліміту відповідальності, необмеженого обов’язку відшкодування чи відмови від судового або колективного захисту.',
        ] },
        { title: 'Скарги та застосовне право', paragraphs: [
          'Скарги щодо сайту надсилайте за контактом нижче з достатніми для перевірки подробицями без зайвих чутливих даних. Ви можете звертатися до компетентного регулятора, належного органу вирішення спорів чи суду без попередньої відмови від законних прав.',
          'Невирішені спори регулюються застосовним правом і розглядаються компетентними за законом судами. Майбутнє положення про вибір права чи суду не може позбавити споживача обов’язкового захисту або суду, доступного йому за законом.',
        ] },
        { title: 'Оновлення та збереження прав', paragraphs: [
          'Кожна редакція має ідентифікатор і, після завершення, дату набрання чинності. Нові умови сайту діють на майбутнє. Публікація змін не переписує укладене замовлення заднім числом і не дозволяє нових платежів чи способів обробки даних.',
          'Істотні зміни чинної послуги потребують погодженого та передбаченого законом порядку повідомлення й вибору. Якщо положення не може законно застосовуватися, решта діє лише в дозволених законом межах. Обидві мовні версії покликані передавати однакові права; обов’язкові правила тлумачення мають пріоритет.',
        ] },
      ],
    },
    privacy: {
      intro: 'Ця політика стосується публічних інформаційних сторінок Natal. До збору додаткових даних застосунком, бронюванням, оплатою чи іншою послугою потрібне окреме повідомлення. Відповідального за ці сторінки оператора має бути зазначено нижче.',
      sections: [
        { title: 'Дані на цих сторінках', paragraphs: [
          'Під час завантаження сторінки хостинг і мережеві провайдери отримують відомості про з’єднання, зокрема IP-адресу, час запиту та потрібний ресурс. Тут немає облікового запису, оплати чи форми звернення. Якщо ви обираєте пошту, телефон або месенджер, одержувач отримує надіслану вами інформацію та відповідні контактні дані.',
          'За дозволеної аналітики ми отримуємо події перегляду й переходу до контактів, випадковий ідентифікатор візиту в пам’яті сторінки, ідентифікатори подій, сторінку та її версію, загальну категорію розміру екрана й рекламне посилання атрибуції за його наявності. У прикладному повідомленні події немає імені, email, повного джерела переходу, IP-адреси чи точної геолокації. Мережеві сервіси все одно бачать дані з’єднання; випадковий ідентифікатор не гарантує анонімності.',
        ] },
        { title: 'Мета та правові підстави', paragraphs: [
          'Завантаження сторінок і пропорційні заходи безпеки служать законному інтересу забезпечити доступність і захист сайту, коли така підстава дозволена та не переважає ваших прав. Відповідь на переддоговірний запит може бути необхідною для дій на вашу вимогу щодо укладення договору; інше листування служить законному інтересу відповісти вам. Окремі записи можуть вимагатися законом.',
          'Необов’язкове вимірювання аудиторії та рекламне вимірювання Meta — окремі згоди. Відмова не обмежує доступ до сторінки. Згода на відстеження не означає згоди на рекламні листи, оплату, нові послуги чи обробку чутливих даних.',
        ] },
        { title: 'Meta та інші одержувачі', paragraphs: [
          'Якщо ви дозволите рекламне вимірювання, Meta Pixel отримуватиме дані перегляду, браузера й з’єднання та може читати чи встановлювати ідентифікатори й пов’язувати активність з обліковим записом Meta. Meta може використовувати дані для вимірювання реклами та власних цілей за своєю політикою. Рекламне вимірювання вимкнене до вашого дозволу.',
          'Google Firebase Hosting надає публічну оболонку; хост застосунку Natal отримує запити сторінок і дозволеного вимірювання. Уповноважені технічні та сервісні постачальники можуть обробляти необхідні для роботи відомості. Поштові, телефонні сервіси, месенджери й магазини отримують дані, коли ви ними користуєтесь. Органи влади чи радники можуть отримувати дані за вимогою закону або для конкретного законного захисту. До завершення політики оператор має підтвердити домовленості з провайдерами та міжнародні передачі.',
        ] },
        { title: 'Строки зберігання та міжнародна передача', paragraphs: [
          'Зберігання вибору у браузері описано в Політиці cookie. Для листування, журналів безпеки, окремих подій, резервних копій та зведених звітів потрібні окремі строки або чіткі критерії видалення. Підтверджений графік і умови передачі мають бути наведені нижче; порожнє поле означає незавершену чернетку, а не негайне видалення чи відсутність передачі за кордон.',
          'Коли закон вимагає гарантій міжнародної передачі, оператор має вказати країни чи напрямки, застосовний механізм та спосіб отримати копію гарантій. Сама згода на необов’язкове відстеження їх не замінює.',
        ] },
        { title: 'Ваш вибір і права', paragraphs: [
          'Налаштування cookie на кожній сторінці дозволяють змінити чи відкликати необов’язкову згоду. Відкликання припиняє майбутній необов’язковий збір у цьому браузері, але не скасовує попередньої законної обробки. Для доступу, виправлення, видалення, обмеження чи переносної копії, коли це застосовно, зверніться за контактом нижче. Права й законні винятки залежать від юрисдикції та обробки.',
          'Право заперечення: ви можете заперечити проти обробки на підставі законного інтересу з причин вашої ситуації, а проти прямого маркетингу — будь-коли. Для перевірки особи можуть бути потрібні пропорційні відомості; перший запит не потребує паспорта. Запити розглядаються у встановлений законом строк із поясненням законного продовження чи відмови.',
        ] },
        { title: 'Скарги', paragraphs: [
          'Ви можете звернутися до належного органу захисту даних: в Україні — Уповноваженого Верховної Ради України з прав людини, у відповідних випадках — наглядового органу ЄЕЗ або Information Commissioner’s Office у Великій Британії. Попереднє звернення до нас необов’язкове та не обмежує права на скаргу.',
        ] },
        { title: 'Діти, чутливі дані та автоматизовані рішення', paragraphs: [
          'Ці сторінки не запитують даних дітей, відомостей про здоров’я, реквізитів карток чи інших чутливих даних. Не надсилайте їх у звичайному зверненні. Майбутня послуга, якій вони потрібні, має надати спеціальне повідомлення та законну підставу до збору.',
          'Ці сторінки не ухвалюють автоматизованих рішень про надання чи відмову в послузі або з подібними істотними наслідками для вас. Згенеровані ілюстрації та демонстрації інтерфейсу — вміст сайту, а не рішення про вас. Нове профілювання чи системи рішень потребують окремого пояснення й належних гарантій.',
        ] },
        { title: 'Оновлення та зв’язок', paragraphs: [
          'Редакцію політики зазначено нижче. Істотні зміни обробки потребують повідомлення до початку нової діяльності та нової згоди, коли вона потрібна. Оновлення не розширює попередню згоду непомітно. Питання приватності надсилайте за контактом нижче, зазначивши сторінку або послугу.',
        ] },
      ],
    },
    cookies: {
      intro: 'Cookie та подібні сховища браузера можуть запам’ятовувати вибір або розпізнавати браузер. Необов’язкове вимірювання аудиторії й реклами вимкнене до вашого вибору. Сайт і політики доступні без обох дозволів.',
      sections: [
        { title: 'Запис вашого вибору', paragraphs: [
          'Після вибору сайт зберігає natal_privacy_preferences_v2 у локальному сховищі цього браузера: версію повідомлення, окремі дозволи аналітики й реклами та час рішення. Ми враховуємо його до 180 днів, після чого запитаємо знову. Налаштування браузера можуть видалити запис раніше. Локальне сховище не очищується автоматично за таймером, тому прострочений запис може залишитися до перезапису чи очищення; він більше не дозволяє відстеження.',
          'Запис потрібен для дотримання вашого вибору, а не для реклами. Якщо сховище заблоковане, вибір діє для поточного сеансу сторінки, а під час наступного відвідування запит може повторитися. Попередній дозвіл лише Meta не вважається згодою на це повідомлення.',
        ] },
        { title: 'Необов’язкове вимірювання аудиторії', paragraphs: [
          'Дозвіл аналітики вмикає власне вимірювання Natal переглядів і переходів до контактів. Ідентифікатор візиту існує лише в пам’яті сторінки та створюється заново після перезавантаження; він не записується до cookie чи локального сховища. Серверні записи можуть залишатися після закриття сторінки відповідно до Політики конфіденційності. Відсутність cookie не виключає застосування правил захисту даних.',
        ] },
        { title: 'Необов’язкове рекламне вимірювання', paragraphs: [
          'Дозвіл реклами вмикає Meta Pixel для вимірювання переглядів. Він може використовувати cookie, зокрема _fbp та _fbc, і відомості про браузер, URL сторінки та з’єднання. Деякі ідентифікатори та строки визначає Meta; вони можуть залежати від браузера й облікового запису. Поточні практики наведені в політиках Meta за посиланнями нижче.',
          'Дозвіл вимірювання аудиторії не дозволяє Meta. Ми не завантажуємо його бібліотеку й не надсилаємо подій Pixel до згоди на рекламу. Зовнішні сервіси, які ви самі відвідуєте, зокрема месенджери чи магазини, керують власною згодою окремо.',
        ] },
        { title: 'Зміна чи відкликання вибору', paragraphs: [
          'Відкрийте Налаштування cookie, змініть два дозволи й збережіть або натисніть Відхилити необов’язкові, щоб вимкнути обидва. Ця кнопка доступна на першій панелі поряд із Дозволити всі. Після відкликання рекламної згоди ми припиняємо нові необов’язкові події, відкликаємо згоду Pixel і видаляємо доступні власні cookie _fbp та _fbc.',
          'Ми не можемо видалити cookie з доменів Meta чи повернути вже надіслану інформацію. Для них використовуйте налаштування браузера чи облікового запису Meta, а для реалізації прав звертайтеся до відповідального володільця даних. Вибір діє в цьому браузері та на цьому сайті; інший пристрій чи очищене сховище можуть потребувати нового вибору.',
        ] },
        { title: 'Зміни політики', paragraphs: [
          'Нові необов’язкові постачальники чи цілі потребують оновлення повідомлення та згоди до ввімкнення. Сама публікація нової політики не дозволяє додаткового відстеження. Цей документ охоплює публічний сайт Natal, а не всі сховища майбутнього застосунку.',
        ] },
      ],
    },
  },
}
