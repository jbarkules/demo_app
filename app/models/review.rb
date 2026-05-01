class Review < ApplicationRecord
  belongs_to :reviewer, class_name: "User"
  belongs_to :reviewee, class_name: "User"

  RATING_RANGE = 1..5

  validates :rating, presence: true, inclusion: { in: RATING_RANGE }
  validates :payment_timeliness, :scope_clarity, :communication,
            inclusion: { in: RATING_RANGE }, allow_nil: true
  validates :body, presence: true, length: { minimum: 20, maximum: 5000 }
  validate  :reviewer_and_reviewee_differ
  validate  :reviewer_must_be_subcontractor
  validate  :reviewee_must_be_developer_or_client

  scope :recent, -> { order(created_at: :desc) }

  private

  def reviewer_and_reviewee_differ
    return if reviewer_id.nil? || reviewee_id.nil?
    errors.add(:reviewee, "can't be the same as reviewer") if reviewer_id == reviewee_id
  end

  def reviewer_must_be_subcontractor
    return unless reviewer
    errors.add(:reviewer, "must be a subcontractor") unless reviewer.subcontractor?
  end

  def reviewee_must_be_developer_or_client
    return unless reviewee
    errors.add(:reviewee, "must be a developer or client") unless reviewee.can_be_reviewed?
  end
end
