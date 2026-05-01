return if Rails.env.production?

password = "password123"

subs = [
  { display_name: "Maria Alvarez",  company_name: "Alvarez Electric",   trade: "Electrical", location: "Austin, TX",  email: "maria@example.com" },
  { display_name: "Tom Becker",     company_name: "Becker Framing",     trade: "Framing",    location: "Denver, CO",  email: "tom@example.com" },
  { display_name: "Priya Shah",     company_name: "Shah Drywall",       trade: "Drywall",    location: "Phoenix, AZ", email: "priya@example.com" }
].map do |attrs|
  User.find_or_create_by!(email_address: attrs[:email]) do |u|
    u.password = password
    u.role = :subcontractor
    u.display_name = attrs[:display_name]
    u.company_name = attrs[:company_name]
    u.trade = attrs[:trade]
    u.location = attrs[:location]
  end
end

devs = [
  { display_name: "Northbrook Homes",   company_name: "Northbrook Homes LLC",  location: "Austin, TX",  email: "northbrook@example.com",
    bio: "Custom residential builder, 12 years in business." },
  { display_name: "Summit Build Group", company_name: "Summit Build Group",    location: "Denver, CO",  email: "summit@example.com",
    bio: "Mid-rise multifamily developer." }
].map do |attrs|
  User.find_or_create_by!(email_address: attrs[:email]) do |u|
    u.password = password
    u.role = :developer
    u.display_name = attrs[:display_name]
    u.company_name = attrs[:company_name]
    u.location = attrs[:location]
    u.bio = attrs[:bio]
  end
end

clients = [
  { display_name: "The Hartmans",  location: "Austin, TX",  email: "hartman@example.com", bio: "Homeowner. Kitchen + bath remodel." },
  { display_name: "Linda Chen",    location: "Phoenix, AZ", email: "lchen@example.com",   bio: "Investor flipping single-family homes." }
].map do |attrs|
  User.find_or_create_by!(email_address: attrs[:email]) do |u|
    u.password = password
    u.role = :client
    u.display_name = attrs[:display_name]
    u.location = attrs[:location]
    u.bio = attrs[:bio]
  end
end

reviews = [
  { reviewer: subs[0], reviewee: devs[0], rating: 5, payment_timeliness: 5, scope_clarity: 4, communication: 5,
    would_work_again: true, project_description: "30-home subdivision, rough electrical",
    body: "Paid every Friday, no chasing. Plans were clean and they answered RFIs same day. Site was always ready when they said it would be." },
  { reviewer: subs[1], reviewee: devs[1], rating: 2, payment_timeliness: 1, scope_clarity: 3, communication: 2,
    would_work_again: false, project_description: "4-story wood frame, 18 weeks",
    body: "Net-90 became net-150 by the end. Change orders piled up and weren't approved until the job was done. Decent people but cash flow killed me." },
  { reviewer: subs[2], reviewee: clients[0], rating: 4, payment_timeliness: 5, scope_clarity: 3, communication: 4,
    would_work_again: true, project_description: "Whole-house drywall, 2,800 sqft",
    body: "Paid on the spot. Scope creep on the ceiling details but they were reasonable about a small change order. Good people." }
]

reviews.each do |attrs|
  Review.find_or_create_by!(reviewer: attrs[:reviewer], reviewee: attrs[:reviewee]) do |r|
    r.rating = attrs[:rating]
    r.payment_timeliness = attrs[:payment_timeliness]
    r.scope_clarity = attrs[:scope_clarity]
    r.communication = attrs[:communication]
    r.would_work_again = attrs[:would_work_again]
    r.project_description = attrs[:project_description]
    r.body = attrs[:body]
  end
end

puts "Seeded #{User.count} users and #{Review.count} reviews."
puts "Sign in as any seeded user with password: #{password}"
