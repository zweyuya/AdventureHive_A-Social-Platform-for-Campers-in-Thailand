export default function Privacy() {
  return (
    <div className="mx-auto max-w-prose px-4 py-10">
      <h1 className="text-2xl font-extrabold">Privacy policy (PDPA)</h1>
      <p className="mt-2 text-sm text-ink/60">How AdventureHive handles your personal data under Thailand's Personal Data Protection Act B.E. 2562.</p>
      <div className="mt-6 space-y-4 text-ink/85">
        <p><strong>What we collect.</strong> Your email, display name, password (stored only as a secure hash), optional profile details, your camping experience and interests, and an optional emergency contact.</p>
        <p><strong>Why.</strong> To run your account, match you with suitable trips, let organizers manage seats, and keep reviews trustworthy.</p>
        <p><strong>Who sees what.</strong> Other members see your display name, city, experience and interests. Your email, phone and birth date are never public. Exact meeting points are shown only to confirmed participants. Your emergency contact is encrypted and visible only to you.</p>
        <p><strong>Your rights.</strong> You can see and edit your data on your profile and delete your account at any time. Deleting erases your personal data; reviews you wrote remain, shown as “Deleted user”.</p>
        <p className="text-sm text-ink/60">This is a student project at the Asian Institute of Technology.</p>
      </div>
    </div>
  );
}
