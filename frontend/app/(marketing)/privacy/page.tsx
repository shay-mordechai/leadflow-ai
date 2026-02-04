export default function PrivacyPage() {
    return (
        <div className="container mx-auto px-4 py-12 max-w-4xl text-gray-800 dark:text-gray-200">
        <h1 className="text-4xl font-bold mb-6 text-blue-600">Privacy Policy</h1>
        <p className="text-sm text-gray-500 mb-8">Last Updated: February 2026</p>

        <div className="space-y-6">
        <section>
        <h2 className="text-xl font-semibold mb-2">1. Data Collection</h2>
        <p>
        We collect information you provide directly to us, such as your name, email address,
        and business details when you register for an account.
        </p>
        </section>

        <section>
        <h2 className="text-xl font-semibold mb-2">2. Call Recordings</h2>
        <p>
        To provide our service, we record and transcribe incoming calls.
        These recordings are stored securely and are only accessible by you.
        </p>
        </section>

        <section>
        <h2 className="text-xl font-semibold mb-2">3. Third-Party Sharing</h2>
        <p>
        We use third-party providers (like Vonage and OpenAI) to process calls.
        We do not sell your data to advertisers.
        </p>
        </section>
        </div>
        </div>
    );
}
