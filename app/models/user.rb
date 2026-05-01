class User < ApplicationRecord
  has_secure_password
  has_many :sessions, dependent: :destroy

  has_many :reviews_written, class_name: "Review", foreign_key: :reviewer_id, dependent: :destroy
  has_many :reviews_received, class_name: "Review", foreign_key: :reviewee_id, dependent: :destroy

  enum :role, { subcontractor: 0, developer: 1, client: 2 }, default: :subcontractor

  normalizes :email_address, with: ->(e) { e.strip.downcase }

  validates :display_name, presence: true, length: { maximum: 80 }
  validates :role, presence: true

  def average_rating
    reviews_received.average(:rating)&.round(2)
  end

  def reviews_count
    reviews_received.count
  end

  def can_be_reviewed?
    developer? || client?
  end

  def can_write_reviews?
    subcontractor?
  end
end
