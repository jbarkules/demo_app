class CreateReviews < ActiveRecord::Migration[8.0]
  def change
    create_table :reviews do |t|
      t.references :reviewer, null: false, foreign_key: { to_table: :users }
      t.references :reviewee, null: false, foreign_key: { to_table: :users }
      t.integer :rating, null: false
      t.integer :payment_timeliness
      t.integer :scope_clarity
      t.integer :communication
      t.boolean :would_work_again
      t.text :body
      t.string :project_description

      t.timestamps
    end

    add_index :reviews, [:reviewer_id, :reviewee_id]
  end
end
