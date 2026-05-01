class AddEngagementToReviews < ActiveRecord::Migration[8.0]
  def change
    add_reference :reviews, :engagement, null: false, foreign_key: true
  end
end
